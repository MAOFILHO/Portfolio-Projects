import asyncio
import json
import subprocess
import sys

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from .. import config
from ..schemas import BenchmarkResult

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

NO_RESULTS_MESSAGE = "No benchmark results yet — run `make benchmark` or POST /api/metrics/run"


def _merged_latest_result() -> BenchmarkResult:
    """Each run only measures whichever backend(s) are actually reachable
    right now (see scripts/benchmark.py's run_all) — once the monolith is
    decommissioned, a run can never measure it again. Naively returning the
    single newest file would make the "before" bar vanish from the Metrics
    page the instant someone migrates, even though that run is still sitting
    on disk. Instead, walk newest-to-oldest and take the latest run that
    measured "monolith" and the latest run that measured "microservices"
    independently, then combine them — so the before/after comparison
    survives even after the monolith is gone. Files that don't match the
    current schema (e.g. saved before the `measured` field existed) are
    skipped, same as if they weren't there."""
    files = sorted(config.RESULTS_DIR.glob("benchmark_*.json"), reverse=True)
    monolith_ops = None
    microservices_ops = None
    latest_generated_at = None

    for path in files:
        try:
            data = BenchmarkResult.model_validate(json.loads(path.read_text()))
        except (json.JSONDecodeError, ValidationError):
            continue
        if latest_generated_at is None:
            latest_generated_at = data.generated_at
        if monolith_ops is None and "monolith" in data.measured:
            monolith_ops = data.monolith
        if microservices_ops is None and "microservices" in data.measured:
            microservices_ops = data.microservices
        if monolith_ops is not None and microservices_ops is not None:
            break

    if monolith_ops is None and microservices_ops is None:
        raise HTTPException(404, NO_RESULTS_MESSAGE)

    measured = [name for name, ops in (("monolith", monolith_ops), ("microservices", microservices_ops)) if ops is not None]
    return BenchmarkResult(
        generated_at=latest_generated_at,
        measured=measured,
        monolith=monolith_ops or [],
        microservices=microservices_ops or [],
    )


@router.get("/latest", response_model=BenchmarkResult)
async def latest_metrics():
    if not config.RESULTS_DIR.exists():
        raise HTTPException(404, NO_RESULTS_MESSAGE)
    return _merged_latest_result()


@router.post("/run", response_model=BenchmarkResult)
async def run_benchmark(requests_per_target: int = 50, concurrency: int = 5):
    script = config.REPO_ROOT / "scripts" / "benchmark.py"
    # subprocess.run() is blocking — running it directly on this async def
    # would freeze the event loop for the whole benchmark duration. That's
    # not just slow: the benchmark subprocess itself calls back into this
    # very server over loopback (GET /api/services) to discover live
    # backend URLs, so a frozen event loop can never answer that request —
    # a self-deadlock only broken by that call's 3s timeout, which silently
    # falls back to bogus localhost URLs (caught for real running this
    # against Azure). asyncio.to_thread keeps the loop free to serve it.
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, str(script), "--requests", str(requests_per_target), "--concurrency", str(concurrency),
         "--bff-url", "http://127.0.0.1:8000"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise HTTPException(500, f"Benchmark failed: {result.stderr[-2000:]}")

    return _merged_latest_result()
