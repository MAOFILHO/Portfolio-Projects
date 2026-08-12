"""MCP server: inference, comparison, and evaluation.

Automates §10–§11 of *Explore and compare models* and §9/§11 of *Fine-tune a
language model* — the playground comparison and the synthetic-dataset evaluation.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server import MCPServer

from app import jobs
from app.config import CANONICAL_TRAVEL_PROMPTS, TRAVEL_SYSTEM_PROMPT, get_settings
from app.schemas.comparison import ComparisonReport, PromptComparison
from app.schemas.evaluation import EVAL_TARGET_INSTRUCTIONS, SYNTHETIC_PROMPT
from app.services import fixtures
from app.services.comparison import score_response

server = MCPServer(
    name="foundry-inference",
    version="0.1.0",
    instructions=(
        "Run inference against Foundry deployments, compare baseline against "
        "fine-tuned models on behaviour, and evaluate a model with a synthetic "
        "dataset scored by AI judges."
    ),
)

#: In-process cache of the most recently created live evaluation run, so
#: get_evaluation_results() returns the same shape whether DEMO_MODE is mock
#: or live — mirroring the _last_live_job_id pattern in foundry_finetune. A
#: live evaluation isn't cheap to regenerate (16 evaluators x N rows of judge
#: calls), so callers are expected to read create_evaluation's own return
#: value directly when possible; this cache exists for callers (like the
#: discovery agent) that call get_evaluation_results() as a separate step.
_last_live_eval: Any = None


def _results_payload(run: Any) -> dict[str, Any]:
    return {
        "name": run.name,
        "target_model": run.target_model,
        "status": run.status,
        "target_tokens": run.target_tokens,
        "overall_score": run.overall_score_display,
        "row_count": run.dataset.row_count,
        "evaluators": [
            {"name": r.name, "group": r.group, "display": r.display, "pass_rate": r.pass_rate}
            for r in run.results
        ],
        "cluster_analysis": (run.cluster_analysis.model_dump() if run.cluster_analysis else None),
        "target_instructions": EVAL_TARGET_INSTRUCTIONS,
    }


async def _complete(
    deployment: str, prompt: str, system_prompt: str, fine_tuned: bool
) -> dict[str, Any]:
    settings = get_settings()
    if settings.is_mock:
        return {
            "content": fixtures.get_chat_response(prompt, fine_tuned=fine_tuned),
            "latency_ms": 3300 if fine_tuned else 2200,
            "tokens": None,
        }
    from app.services import azure_foundry

    # azure_foundry's client is the sync OpenAI SDK, and this call can take
    # several seconds — running it directly would block the single asyncio
    # event loop for its duration, starving every other request (including
    # /agent/jobs/{id} progress polling) until it returns. to_thread offloads
    # it to a worker thread instead; contextvars (see app/jobs.py) still
    # propagate into that thread automatically.
    return await asyncio.to_thread(azure_foundry.chat_completion, deployment, prompt, system_prompt)


@server.tool(description="Send one prompt to a deployment and return the completion.")
async def chat_completion(
    prompt: str,
    deployment: str = "",
    system_prompt: str = "",
    fine_tuned: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    target = deployment or settings.model_baseline
    system = system_prompt or TRAVEL_SYSTEM_PROMPT
    result = await _complete(target, prompt, system, fine_tuned)
    return {
        "deployment": target,
        "prompt": prompt,
        "system_prompt": system,
        "response": result["content"],
        "latency_ms": result.get("latency_ms"),
        "tokens": result.get("tokens"),
    }


@server.tool(
    description=(
        "Compare a baseline deployment against a fine-tuned one across prompts, "
        "scoring each response on behaviour (tone, restricted recommendations, "
        "follow-up question) rather than string equality. Omit prompts to use "
        "the five canonical travel prompts from the lab."
    )
)
async def compare_completions(
    prompts: list[str] | None = None,
    baseline_deployment: str = "",
    fine_tuned_deployment: str = "",
) -> dict[str, Any]:
    settings = get_settings()
    baseline = baseline_deployment or settings.model_baseline
    tuned = fine_tuned_deployment
    if not tuned:
        if settings.is_mock:
            tuned = fixtures.get_finetune_job().deployment_name or f"{settings.model_baseline}-ft"
        else:
            # Never guess a deployment name against real Azure — a wrong guess
            # is a confusing 404, not a helpful default. A live SFT job takes
            # ~60 min to reach `succeeded` and auto-deploy; call get_job_status
            # first and pass its `deployment_name` once that's non-null.
            return {
                "error": (
                    "no fine_tuned_deployment given and no completed, deployed "
                    "fine-tuned model available yet — check get_job_status first"
                )
            }
    selected = list(prompts) if prompts else list(CANONICAL_TRAVEL_PROMPTS)

    comparisons: list[PromptComparison] = []
    for i, prompt in enumerate(selected, start=1):
        jobs.report(f"comparison: prompt {i}/{len(selected)} — {prompt[:60]}")
        base_result = await _complete(baseline, prompt, TRAVEL_SYSTEM_PROMPT, fine_tuned=False)
        tuned_result = await _complete(tuned, prompt, TRAVEL_SYSTEM_PROMPT, fine_tuned=True)
        comparisons.append(
            PromptComparison(
                prompt=prompt,
                system_prompt=TRAVEL_SYSTEM_PROMPT,
                baseline=score_response(
                    baseline,
                    base_result["content"],
                    base_result.get("latency_ms"),
                    base_result.get("tokens"),
                ),
                fine_tuned=score_response(
                    tuned,
                    tuned_result["content"],
                    tuned_result.get("latency_ms"),
                    tuned_result.get("tokens"),
                ),
            )
        )

    report = ComparisonReport(
        baseline_model=baseline, fine_tuned_model=tuned, comparisons=comparisons
    )
    return report.model_dump()


@server.tool(
    description=(
        "Generate a synthetic evaluation dataset of travel questions including "
        "content-safety and prompt-injection probes."
    )
)
async def generate_synthetic_dataset(
    row_count: int = 0, deployment: str = "", prompt: str = ""
) -> dict[str, Any]:
    settings = get_settings()
    rows = row_count or settings.eval_row_count
    target = deployment or settings.model_compare_a

    if settings.is_mock:
        dataset = fixtures.get_synthetic_dataset()
        trimmed = dataset.model_copy(update={"rows": dataset.rows[:rows]})
        return trimmed.model_dump(by_alias=True)

    from app.services import azure_foundry

    dataset = await asyncio.to_thread(
        azure_foundry.generate_synthetic_dataset, target, rows, prompt or SYNTHETIC_PROMPT
    )
    return dataset.model_dump(by_alias=True)


@server.tool(
    description=(
        "Run an evaluation over a synthetic dataset using the 16 standard AI-judge "
        "evaluators across Quality, Safety, Business, and Agents groups."
    )
)
async def create_evaluation(
    deployment: str = "", row_count: int = 0, include_agent_evaluators: bool | None = None
) -> dict[str, Any]:
    settings = get_settings()
    target = deployment or settings.model_compare_a
    include_agents = (
        settings.include_agent_evaluators
        if include_agent_evaluators is None
        else include_agent_evaluators
    )

    if settings.is_mock:
        run = fixtures.get_evaluation_run()
        if not include_agents:
            run = run.model_copy(
                update={"results": [r for r in run.results if r.group != "Agents"]}
            )
        return run.model_dump(by_alias=True)

    from app.services import azure_foundry

    dataset = await asyncio.to_thread(
        azure_foundry.generate_synthetic_dataset, target, row_count or settings.eval_row_count
    )
    run = await asyncio.to_thread(azure_foundry.create_evaluation, target, dataset, include_agents)
    global _last_live_eval
    _last_live_eval = run
    return run.model_dump(by_alias=True)


@server.tool(description="Get evaluation results, including per-evaluator pass rates.")
async def get_evaluation_results(run_name: str = "travel-assistant-eval") -> dict[str, Any]:
    settings = get_settings()
    if not settings.is_mock:
        if _last_live_eval is None:
            return {"error": "no evaluation yet this run — call create_evaluation first"}
        return _results_payload(_last_live_eval)

    return _results_payload(fixtures.get_evaluation_run())


if __name__ == "__main__":
    server.run(transport="stdio")
