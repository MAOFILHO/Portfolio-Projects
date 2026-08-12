"""Live Azure AI Foundry adapter.

Mirrors `fixtures.py` call-for-call, so `DEMO_MODE` swaps the backing store
without the agent graph or MCP tool schemas noticing.

Only reached when `DEMO_MODE=live`. Every call here bills real tokens.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from app import jobs
from app.config import Settings, get_settings
from app.schemas.evaluation import (
    EVAL_TARGET_INSTRUCTIONS,
    SYNTHETIC_PROMPT,
    EvaluationRun,
    EvaluatorResult,
    SyntheticDataset,
    SyntheticRow,
    default_evaluators,
)
from app.schemas.finetune import FineTuneJob, FineTuneJobConfig, JobLogEntry, JobStatus


class FoundryUnavailableError(RuntimeError):
    """Raised when live mode is requested but the environment cannot support it."""


@lru_cache
def _client(settings: Settings | None = None) -> Any:
    """Build an Azure-OpenAI-compatible client against the Foundry endpoint."""
    cfg = settings or get_settings()
    cfg.require_live_credentials()

    try:
        from openai import AzureOpenAI
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        raise FoundryUnavailableError("openai package is not installed") from exc

    # 2025-04-01-preview is the earliest version that accepts `trainingType`
    # (Developer/Standard/GlobalStandard) on fine-tuning job creation — the
    # 2024-10-21 GA surface silently defaults to Standard, which gpt-4.1
    # does not support for Supervised fine-tuning. See CHANGELOG.md.
    api_version = "2025-04-01-preview"

    if cfg.azure_foundry_api_key:
        return AzureOpenAI(
            azure_endpoint=cfg.azure_foundry_endpoint,
            api_key=cfg.azure_foundry_api_key,
            api_version=api_version,
        )

    # No key configured: fall back to Entra ID (the recommended path).
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    except ImportError as exc:  # pragma: no cover
        raise FoundryUnavailableError("azure-identity is not installed") from exc

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=cfg.azure_foundry_endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version,
    )


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
def chat_completion(
    deployment: str,
    prompt: str,
    system_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 800,
) -> dict[str, Any]:
    """One chat completion against a deployment. Bills tokens."""
    client = _client()
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_completion_tokens=max_tokens,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    usage = response.usage
    return {
        "content": response.choices[0].message.content or "",
        "latency_ms": elapsed_ms,
        "tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


# ---------------------------------------------------------------------------
# Fine-tuning
# ---------------------------------------------------------------------------
#: A tiny 10-row JSONL file processes in well under this in practice; this is
#: a safety ceiling, not the expected wait.
_FILE_PROCESSING_TIMEOUT_S = 60


def upload_training_file(path: str) -> str:
    """Upload a JSONL file for fine-tuning; returns the file id.

    Waits for the file to reach Azure's `processed` state before returning.
    Skipping this and immediately referencing the file id in create_sft_job
    is a real race: Azure accepts the upload synchronously but validates the
    file asynchronously, so a job created against an unprocessed file fails
    with a confusing "must point to a completed file import" 400 — reproduced
    live, not theoretical.
    """
    client = _client()
    with open(path, "rb") as handle:
        uploaded = client.files.create(file=handle, purpose="fine-tune")

    deadline = time.monotonic() + _FILE_PROCESSING_TIMEOUT_S
    status = uploaded.status
    while status not in ("processed", "error") and time.monotonic() < deadline:
        jobs.report(f"waiting for training file to finish processing (status: {status})")
        time.sleep(2)
        status = client.files.retrieve(uploaded.id).status

    if status == "error":
        raise FoundryUnavailableError(f"training file {uploaded.id} failed processing on Azure")
    if status != "processed":
        raise FoundryUnavailableError(
            f"training file {uploaded.id} did not finish processing within "
            f"{_FILE_PROCESSING_TIMEOUT_S}s (status: {status})"
        )
    return uploaded.id


#: Azure's `trainingType` request field uses its own casing, distinct from
#: this project's `FineTuneJobConfig.training_type` literal ("Developer" /
#: "Global" / "Regional"). Verified live against the 2025-04-01-preview API:
#: passing "Developer" (or omitting the field) is silently accepted as
#: "Standard", which gpt-4.1 doesn't support for Supervised fine-tuning — the
#: request only succeeds with the exact string "developerTier" below. Global
#: and Regional are unverified live (this project only ever submits
#: Developer, see COSTS.md); best-effort mapped from Microsoft Learn docs.
_AZURE_TRAINING_TYPE = {
    "Developer": "developerTier",
    "Global": "globalStandard",
    "Regional": "standard",
}


def create_sft_job(config: FineTuneJobConfig, training_file_id: str) -> FineTuneJob:
    """Submit a supervised fine-tuning job.

    Hyperparameters are sent explicitly rather than relying on service defaults,
    so a rerun is reproducible (see PLAN.md contradiction #6).
    """
    client = _client()
    job = client.fine_tuning.jobs.create(
        model=config.qualified_base_model,
        training_file=training_file_id,
        suffix=config.suffix,
        hyperparameters={
            "n_epochs": config.hyperparameters.n_epochs,
            "batch_size": config.hyperparameters.batch_size,
            "learning_rate_multiplier": config.hyperparameters.learning_rate_multiplier,
        },
        seed=config.hyperparameters.seed,
        # Azure-specific extension, not in the OpenAI SDK's typed params —
        # must be passed via extra_body.
        extra_body={
            "trainingType": _AZURE_TRAINING_TYPE.get(config.training_type, config.training_type)
        },
    )
    return _to_job(job, config)


def get_job_status(job_id: str) -> FineTuneJob:
    client = _client()
    return _to_job(client.fine_tuning.jobs.retrieve(job_id), FineTuneJobConfig())


#: Azure's deployment SKU name, distinct from this project's
#: `ft_deployment_type` setting ("Developer" / "GlobalStandard" / "Standard").
#: The ARM control-plane deployment resource expects "DeveloperTier", not
#: "Developer" — see infra/terraform/modules/model_deployment/main.tf, which
#: passes this exact string for the same reason.
_AZURE_DEPLOYMENT_SKU = {
    "Developer": "DeveloperTier",
    "GlobalStandard": "GlobalStandard",
    "Standard": "Standard",
}


def _arm_deployments_base_url() -> tuple[str, dict[str, str]]:
    """Shared ARM auth/URL setup for the Cognitive Services deployments API."""
    from azure.identity import DefaultAzureCredential

    cfg = get_settings()
    cfg.require_live_credentials()
    if not cfg.azure_subscription_id or not cfg.azure_resource_group:
        raise FoundryUnavailableError(
            "AZURE_SUBSCRIPTION_ID and AZURE_RESOURCE_GROUP must be set for live ARM calls"
        )
    account_name = cfg.azure_foundry_endpoint.rstrip("/").split("//", 1)[-1].split(".", 1)[0]
    token = DefaultAzureCredential().get_token("https://management.azure.com/.default").token
    base = (
        "https://management.azure.com/subscriptions/"
        f"{cfg.azure_subscription_id}/resourceGroups/{cfg.azure_resource_group}"
        f"/providers/Microsoft.CognitiveServices/accounts/{account_name}/deployments"
    )
    return base, {"Authorization": f"Bearer {token}"}


def deploy_model(deployment_name: str, model_name: str, sku: str = "Developer") -> dict[str, Any]:
    """Create (or update) a Cognitive Services deployment for a fine-tuned model.

    This is an ARM control-plane operation, not part of the OpenAI-compatible
    data-plane surface the rest of this module uses — fine-tuned models don't
    get deployed automatically unless the job itself set auto-deploy (this
    project's create_sft_job does not), so a live deployment must be created
    explicitly here.
    """
    import httpx

    base, headers = _arm_deployments_base_url()
    sku_name = _AZURE_DEPLOYMENT_SKU.get(sku, sku)
    url = f"{base}/{deployment_name}?api-version=2024-10-01"
    body = {
        "sku": {"name": sku_name, "capacity": 1},
        "properties": {"model": {"format": "OpenAI", "name": model_name, "version": "1"}},
    }
    response = httpx.put(url, json=body, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def list_finetuned_deployments() -> list[dict[str, Any]]:
    """List existing Cognitive Services deployments whose model is fine-tuned.

    Used as a fallback when the in-process job/deployment cache (see
    mcp_servers/foundry_finetune/server.py's _last_live_job_id /
    _last_live_deployment) is empty — e.g. after a server restart — but a
    real, working deployment already exists on Azure. Without this, a
    perfectly good deployment becomes invisible to Workflow 3 just because
    the process that created it isn't the one currently running; that's a
    real gap this project hit live, not a hypothetical one.

    Azure names a fine-tuned model like
    "gpt-4.1-2025-04-14.ft-<jobid>-<suffix>" — the ".ft-" segment is what
    distinguishes it from a base catalog model (e.g. plain "gpt-4.1").
    """
    import httpx

    base, headers = _arm_deployments_base_url()
    response = httpx.get(f"{base}?api-version=2024-10-01", headers=headers, timeout=30)
    response.raise_for_status()

    results: list[dict[str, Any]] = []
    for item in response.json().get("value", []):
        props = item.get("properties", {})
        model_name = props.get("model", {}).get("name", "")
        if ".ft-" not in model_name:
            continue
        results.append(
            {
                "deployment_name": item.get("name"),
                "model_name": model_name,
                "provisioning_state": props.get("provisioningState"),
                "created_at": item.get("systemData", {}).get("createdAt", ""),
            }
        )
    results.sort(key=lambda d: d["created_at"], reverse=True)
    return results


def get_job_logs(job_id: str, limit: int = 200) -> list[JobLogEntry]:
    client = _client()
    events = client.fine_tuning.jobs.list_events(fine_tuning_job_id=job_id, limit=limit)
    entries: list[JobLogEntry] = []
    for event in events.data:
        entries.append(
            JobLogEntry(
                status=getattr(event, "level", "info"),
                type="metrics" if "loss" in (event.message or "") else "message",
                message=event.message or "",
            )
        )
    return entries


_STATUS_MAP = {
    "validating_files": JobStatus.QUEUED,
    "queued": JobStatus.QUEUED,
    "running": JobStatus.RUNNING,
    "succeeded": JobStatus.SUCCEEDED,
    "failed": JobStatus.FAILED,
    "cancelled": JobStatus.CANCELLED,
}


def _to_job(raw: Any, config: FineTuneJobConfig) -> FineTuneJob:
    """Map an SDK job object onto our schema."""
    return FineTuneJob(
        id=raw.id,
        name=getattr(raw, "fine_tuned_model", None) or raw.id,
        status=_STATUS_MAP.get(raw.status, JobStatus.QUEUED),
        config=config,
        fine_tuned_model=getattr(raw, "fine_tuned_model", None),
        error=getattr(getattr(raw, "error", None), "message", None),
    )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def generate_synthetic_dataset(
    deployment: str, row_count: int, prompt: str = SYNTHETIC_PROMPT
) -> SyntheticDataset:
    """Generate an evaluation dataset by asking the model for questions.

    Foundry's portal has a first-class synthetic-generation feature; the public
    SDK surface for it is not stable, so we reproduce its behaviour explicitly:
    ask the target deployment to produce the questions, then answer each one.
    """
    client = _client()
    listing = client.chat.completions.create(
        model=deployment,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate evaluation datasets. Reply with one question per "
                    "line and no numbering, commentary, or blank lines."
                ),
            },
            {"role": "user", "content": f"{prompt}. Produce exactly {row_count} questions."},
        ],
        temperature=1.0,
        max_completion_tokens=2000,
    )
    questions = [
        q.strip(" -•\t")
        for q in (listing.choices[0].message.content or "").splitlines()
        if q.strip()
    ][:row_count]

    rows: list[SyntheticRow] = []
    for idx, question in enumerate(questions, start=1):
        jobs.report(f"generating dataset row {idx}/{len(questions)}")
        answer = chat_completion(deployment, question, EVAL_TARGET_INSTRUCTIONS)
        rows.append(
            SyntheticRow(
                id=str(idx),
                query=question,
                **{"sample.output_text": answer["content"]},
                test_case_description="Synthetically generated evaluation row.",
            )
        )

    return SyntheticDataset(
        name=f"{deployment.replace('.', '_').replace('-', '_')}_live",
        rows=rows,
        prompt=prompt,
    )


def create_evaluation(
    deployment: str, dataset: SyntheticDataset, include_agents: bool = True
) -> EvaluationRun:
    """Score a dataset with the standard evaluator set.

    Uses the target model as judge (LLM-as-judge), matching the portal's
    "AI model as a judge" description in §11.4.
    """
    names = default_evaluators(include_agents)
    from app.schemas.evaluation import EVALUATOR_GROUPS

    group_of = {n: g for g, members in EVALUATOR_GROUPS.items() for n in members}

    results: list[EvaluatorResult] = []
    for i, name in enumerate(names, start=1):
        jobs.report(f"evaluator {i}/{len(names)}: {name} — scoring {len(dataset.rows)} rows")
        passed = _judge_rows(deployment, dataset, name)
        jobs.report(f"evaluator {i}/{len(names)}: {name} — {passed}/{len(dataset.rows)} passed")
        results.append(
            EvaluatorResult(name=name, group=group_of[name], passed=passed, total=len(dataset.rows))
        )

    return EvaluationRun(
        target_model=deployment,
        dataset=dataset,
        status="completed",
        results=results,
    )


def _judge_rows(deployment: str, dataset: SyntheticDataset, evaluator: str) -> int:
    """Ask the judge model to pass/fail every row for one evaluator."""
    import openai

    client = _client()
    passed = 0
    for row in dataset.rows:
        try:
            verdict = client.chat.completions.create(
                model=deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are the '{evaluator}' evaluator. Judge whether the "
                            "response satisfies this criterion. Reply with exactly one "
                            "word: PASS or FAIL."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Query: {row.query}\n\nResponse: {row.sample_output_text}",
                    },
                ],
                temperature=0.0,
                max_completion_tokens=5,
            )
        except openai.BadRequestError as exc:
            # The dataset deliberately includes content-safety/security probe
            # rows (see SYNTHETIC_PROMPT) — Azure's own RAI filter sometimes
            # blocks the *judge* call itself on one of those rows. Treat a
            # content-filtered judge call as a FAIL for this row rather than
            # aborting the whole 16-evaluator x 45-row run over one row.
            body = getattr(exc, "body", None) or {}
            if isinstance(body, dict) and body.get("code") == "content_filter":
                continue
            raise
        if "PASS" in (verdict.choices[0].message.content or "").upper():
            passed += 1
    return passed
