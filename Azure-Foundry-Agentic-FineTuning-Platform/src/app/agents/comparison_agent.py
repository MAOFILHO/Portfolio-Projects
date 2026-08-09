"""Comparison sub-agent — Demo 3.

Runs the same prompts against the baseline and the fine-tuned deployment under
an identical system message, then scores both on behaviour.

The identical system message is the point: it is the same string the training
data carries on every row, which is what makes the comparison fair.
"""

from __future__ import annotations

from typing import Any

from app.agents.state import AgentState
from app.config import CANONICAL_TRAVEL_PROMPTS, get_settings
from app.mcp_clients.registry import call_tool
from app.telemetry import span


async def run_comparison(state: AgentState) -> dict[str, Any]:
    settings = get_settings()
    trace: list[str] = []

    # A free-text request becomes a single-prompt comparison; otherwise use the
    # five canonical prompts from the guide.
    request = (state.get("request") or "").strip()
    use_custom = bool(request) and request.lower() not in {
        "comparison",
        "compare",
        "demo3",
        "demo 3",
    }
    prompts = [request] if use_custom else list(CANONICAL_TRAVEL_PROMPTS)

    with span(
        "agent.comparison", demo="comparison", mode=settings.demo_mode, prompt_count=len(prompts)
    ):
        with span("mcp.get_job_status"):
            job = await call_tool("get_job_status", {})
            fine_tuned_deployment = job.get("deployment_name") or ""
            trace.append(f"resolved fine-tuned deployment → {fine_tuned_deployment or '(none yet)'}")

        with span("mcp.compare_completions"):
            report = await call_tool(
                "compare_completions",
                {
                    "prompts": prompts,
                    "baseline_deployment": settings.model_baseline,
                    "fine_tuned_deployment": fine_tuned_deployment,
                },
            )

        if error := report.get("error"):
            # Expected, not exceptional: a live SFT job takes ~60 min to reach
            # `succeeded` and auto-deploy. Report this plainly instead of
            # crashing on a missing key — re-run Workflow 3 once the job (see
            # Workflow 2's job_id) has completed.
            trace.append(f"compare_completions → {error}")
            return {
                "result": {"demo": "comparison", "error": error, "prompts": prompts},
                "trace": trace,
                "error": error,
            }

        trace.append(
            f"compare_completions → fine-tuned {report['fine_tuned_total']}"
            f"/{report['max_total']} vs baseline {report['baseline_total']}"
            f"/{report['max_total']}"
        )

    return {
        "result": {
            "demo": "comparison",
            "report": report,
            "prompts": prompts,
        },
        "trace": trace,
    }
