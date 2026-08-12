"""Fine-tune sub-agent — Demo 2.

Owns the supervised fine-tuning lifecycle (guide §8–§10): validate the training
file, estimate cost, upload, submit, monitor, and report the deployment.

Cost is estimated *before* submission, deliberately — a fine-tune is the one
irreversible spend in this project.
"""

from __future__ import annotations

from typing import Any

from app.agents.state import AgentState
from app.config import get_settings
from app.mcp_clients.registry import call_tool
from app.telemetry import span


async def run_finetune(state: AgentState) -> dict[str, Any]:
    settings = get_settings()
    trace: list[str] = []

    with span("agent.finetune", demo="finetune", mode=settings.demo_mode):
        with span("mcp.validate_jsonl"):
            validation = await call_tool("validate_jsonl", {})
            trace.append(
                f"validate_jsonl → {validation['valid_rows']}/"
                f"{validation['total_lines']} rows valid"
            )

        if not validation.get("is_valid"):
            # Surface the schema violations rather than swallowing them; the UI
            # renders these as a demonstrated feature.
            return {
                "result": {
                    "demo": "finetune",
                    "validation": validation,
                    "blocked": True,
                },
                "trace": trace + ["blocked: training file failed validation"],
                "error": "training file failed validation",
            }

        with span("mcp.estimate_training_cost"):
            estimate = await call_tool(
                "estimate_training_cost",
                {"billed_tokens": 16000, "epochs": settings.ft_n_epochs},
            )
            trace.append(f"estimate_training_cost → ${estimate['estimated_usd']}")

        with span("mcp.upload_training_file"):
            upload = await call_tool("upload_training_file", {})
            trace.append(f"upload_training_file → {upload['file_id']}")

        with span("mcp.create_sft_job"):
            job = await call_tool("create_sft_job", {"training_file_id": upload["file_id"]})
            trace.append(f"create_sft_job → {job['job_id']} ({job['status']})")

        with span("mcp.get_job_status"):
            status = await call_tool("get_job_status", {"job_id": job["job_id"]})
            trace.append(f"get_job_status → {status['status']} {status['progress_pct']}%")

        with span("mcp.get_job_logs"):
            logs = await call_tool("get_job_logs", {"job_id": job["job_id"], "limit": 12})
            trace.append(f"get_job_logs → {logs['total_available']} entries")

        with span("mcp.deploy_finetuned_model", sku=settings.ft_deployment_type):
            deployment = await call_tool("deploy_finetuned_model", {})
            if deploy_error := deployment.get("error"):
                # Expected, not exceptional: a live SFT job takes ~60 min to
                # reach `succeeded` before it can be deployed, so a deploy
                # attempted immediately after submission in this same run
                # will essentially always still be too early. Report it
                # plainly and keep the rest of this run's results (job
                # submitted, status, logs) rather than crashing on a key that
                # only exists on a successful deploy — re-run this workflow
                # later (or add a standalone "deploy" trigger) once the job
                # has actually completed.
                trace.append(f"deploy_finetuned_model → not yet: {deploy_error}")
                deployment = None
            else:
                trace.append(
                    f"deploy_finetuned_model → {deployment['deployment_type']} "
                    f"(${deployment['hourly_cost_usd']}/hr)"
                )

    return {
        "result": {
            "demo": "finetune",
            "validation": validation,
            "cost_estimate": estimate,
            "upload": upload,
            "job": job,
            "status": status,
            "logs": logs,
            "deployment": deployment,
            "blocked": False,
        },
        "trace": trace,
    }
