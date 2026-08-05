"""In-memory (with disk-backed persistence) background job execution for
on-demand model runs.

Model fits/training are blocking, CPU-bound calls (seconds for SARIMAX, up to
a couple of minutes for auto_arima's full grid search, tens of seconds for
either LSTM's training epochs) -- too slow to run synchronously inside a
request and must not block the event loop. A ThreadPoolExecutor plus an
in-memory job dict handles execution; each job's state is also written to
outputs/jobs/{id}.json on every transition, so job status/history survives a
backend restart. A job that was still queued/running at the moment of a
restart is marked failed on reload, since the thread that was running it no
longer exists -- there is no way to resume in-flight work across a process
restart, only to report accurately that it was interrupted.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Callable, Literal

logger = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass
class Job:
    id: str
    model_key: str
    status: JobStatus = "queued"
    result: dict | None = None
    error: str | None = None
    submitted_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None


_JOB_FIELDS = {f.name for f in fields(Job)}
_executor = ThreadPoolExecutor(max_workers=2)
_jobs: dict[str, Job] = {}
_jobs_dir: Path | None = None


def init_job_store(output_dir: Path) -> None:
    """Point the job store at a directory and reload any previously
    persisted jobs. Call once at API startup."""
    global _jobs_dir
    _jobs_dir = output_dir / "jobs"
    _jobs_dir.mkdir(parents=True, exist_ok=True)

    loaded = 0
    for path in sorted(_jobs_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Skipping unreadable job file %s", path)
            continue

        job = Job(**{k: v for k, v in data.items() if k in _JOB_FIELDS})
        if job.status in ("queued", "running"):
            job.status = "failed"
            job.error = "Job was interrupted by a server restart."
            job.finished_at = time.time()
            _persist(job)
        _jobs[job.id] = job
        loaded += 1

    logger.info("Job store initialized at %s (%d persisted job(s) loaded)", _jobs_dir, loaded)


def _persist(job: Job) -> None:
    if _jobs_dir is None:
        return
    path = _jobs_dir / f"{job.id}.json"
    path.write_text(json.dumps(asdict(job), indent=2))


def submit_job(model_key: str, run_fn: Callable[[], dict]) -> Job:
    """Kick off `run_fn` in a background thread and return the tracking Job immediately."""
    job = Job(id=str(uuid.uuid4()), model_key=model_key)
    _jobs[job.id] = job
    _persist(job)

    def _execute() -> None:
        job.status = "running"
        job.started_at = time.time()
        _persist(job)
        try:
            job.result = run_fn()
            job.status = "completed"
            logger.info("Job %s (%s) completed", job.id, model_key)
        except Exception as exc:  # surface any model failure to the API rather than crash the worker
            logger.exception("Job %s (%s) failed", job.id, model_key)
            job.error = str(exc)
            job.status = "failed"
        finally:
            job.finished_at = time.time()
            _persist(job)

    _executor.submit(_execute)
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def latest_job_for_model(model_key: str) -> Job | None:
    matches = [j for j in _jobs.values() if j.model_key == model_key]
    if not matches:
        return None
    return max(matches, key=lambda j: j.submitted_at)
