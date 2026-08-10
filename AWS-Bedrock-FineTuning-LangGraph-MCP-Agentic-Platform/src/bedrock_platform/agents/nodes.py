"""The four sub-agents, one function per node.

Each node calls tools **through** `call_tool`, which enforces the per-agent allowlist at
call time. A node never imports an AWS client directly — that would bypass the allowlist
and make the invariant unverifiable.

Nodes mutate only `GraphState`, and every value they write is a typed Pydantic model.
"""

import contextlib
from collections.abc import Callable
from typing import Any

from bedrock_platform.agents.state import (
    CostFacts,
    DatasetFacts,
    EvalFacts,
    GraphState,
    JobFacts,
    NodeName,
)
from bedrock_platform.mcp import server_bedrock, server_dataset, server_eval
from bedrock_platform.mcp.allowlist import assert_tool_allowed
from bedrock_platform.observability.langfuse_setup import trace_step

TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    "validate_dataset": server_dataset.validate_dataset,
    "split_dataset": server_dataset.split_dataset,
    "estimate_training_cost": server_dataset.estimate_training_cost,
    "start_finetune_job": server_bedrock.start_finetune_job,
    "get_job_status": server_bedrock.get_job_status,
    "read_training_metrics": server_bedrock.read_training_metrics,
    "invoke_base_model": server_bedrock.invoke_base_model,
    "invoke_tuned_model": server_bedrock.invoke_tuned_model,
    "score_output": server_eval.score_output,
}


# These emit their own `generation` observation inside the tool, carrying model name and
# token usage. Wrapping them in a `tool` span too would double-represent one call as
# sibling dispatch + execution nodes, which Langfuse explicitly warns against.
SELF_TRACED_TOOLS: frozenset[str] = frozenset({"invoke_base_model", "invoke_tuned_model"})


def call_tool(agent: str, tool_name: str, payload: Any) -> Any:
    """The single dispatch point for every agent tool call.

    Routing all calls through here is what makes the allowlist an enforced control rather
    than a convention — there is no second path to a tool. It is also the one place every
    tool call can be traced, so the Langfuse tree shows which agent called which tool.
    """
    assert_tool_allowed(agent, tool_name)
    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        raise KeyError(f"tool {tool_name!r} is allowlisted but not registered")
    if tool_name in SELF_TRACED_TOOLS:
        return tool(payload)
    with trace_step(
        tool_name, as_type="tool", input=payload.model_dump(), called_by=agent
    ) as observation:
        result = tool(payload)
        if observation is not None:
            # Tracing must never break the call it is observing.
            with contextlib.suppress(Exception):
                observation.update(output=result.model_dump())
        return result


def dataset_prep(state: GraphState) -> GraphState:
    """Validates and splits the dataset, then prices the run. Read-only against AWS."""
    agent: NodeName = "dataset_prep"
    with trace_step(
        agent,
        as_type="agent",
        input={"scenario_id": state.scenario_id, "dry_run": state.dry_run},
    ):
        state.record_visit(agent)

        validation = call_tool(
            agent,
            "validate_dataset",
            server_dataset.ValidateDatasetInput(scenario_id=state.scenario_id),
        )
        split = call_tool(
            agent,
            "split_dataset",
            server_dataset.SplitDatasetInput(scenario_id=state.scenario_id),
        )
        state.dataset = DatasetFacts(
            record_count=validation.record_count,
            train_count=split.train_count,
            validation_count=split.validation_count,
            invalid_line_numbers=validation.invalid_line_numbers,
            estimated_training_tokens=validation.estimated_training_tokens,
        )

        if validation.invalid_line_numbers:
            state.errors.append(
                f"{len(validation.invalid_line_numbers)} invalid records in "
                f"{state.scenario_id} dataset"
            )

        try:
            cost = call_tool(
                agent,
                "estimate_training_cost",
                server_dataset.EstimateCostInput(
                    scenario_id=state.scenario_id,
                    training_tokens=validation.estimated_training_tokens,
                ),
            )
            state.cost = CostFacts(
                training_cost_usd=cost.training_cost_usd,
                storage_cost_usd_per_month=cost.storage_cost_usd_per_month,
                one_time_cost_usd=cost.one_time_cost_usd,
            )
        except Exception as exc:  # noqa: BLE001 - a pricing outage must not look free
            # Refusing to quote beats quoting wrong: leaving cost unset blocks the
            # downstream approval display rather than showing $0.00.
            state.errors.append(f"cost estimate unavailable: {type(exc).__name__}: {exc}")

    return state


def finetune_supervisor(state: GraphState) -> GraphState:
    """The only node that can spend money, and only with a human approval token."""
    agent: NodeName = "finetune_supervisor"
    with trace_step(
        agent,
        as_type="agent",
        input={"scenario_id": state.scenario_id, "dry_run": state.dry_run},
    ):
        state.record_visit(agent)

        started = call_tool(
            agent,
            "start_finetune_job",
            server_bedrock.StartFinetuneInput(
                scenario_id=state.scenario_id,
                approval_token=state.approval_token,
                dry_run=state.dry_run,
            ),
        )
        state.job = JobFacts(job_arn=started.job_arn)

        if started.job_arn is None:
            return state

        status = call_tool(
            agent,
            "get_job_status",
            server_bedrock.JobStatusInput(job_identifier=started.job_arn),
        )
        state.job = JobFacts(
            job_arn=started.job_arn,
            status=status.status,
            validation_status=status.validation_status,
            training_status=status.training_status,
            output_model_arn=status.output_model_arn,
            failure_message=status.failure_message,
        )
    return state


def evaluation(state: GraphState) -> GraphState:
    """Scores stored outputs. Read-only, and never invokes a model itself — scoring and
    generating are separate agents so a scorer cannot spend inference budget."""
    agent: NodeName = "evaluation"
    with trace_step(agent, as_type="agent", input={"scenario_id": state.scenario_id}):
        state.record_visit(agent)
        facts = EvalFacts()

        if state.dry_run:
            facts.notes.append("dry run — no outputs scored")
            state.evaluation = facts
            return state

        if state.job is None or state.job.job_arn is None:
            facts.notes.append("no job to read metrics from")
            state.evaluation = facts
            return state

        metrics = call_tool(
            agent,
            "read_training_metrics",
            server_bedrock.TrainingMetricsInput(
                scenario_id=state.scenario_id, job_identifier=state.job.job_arn
            ),
        )
        if metrics.training_loss:
            facts.notes.append(
                f"training loss {metrics.training_loss[0]:.4f} -> {metrics.training_loss[-1]:.4f}"
            )
        if metrics.validation_loss:
            facts.notes.append(
                f"validation loss {metrics.validation_loss[0]:.4f} -> "
                f"{metrics.validation_loss[-1]:.4f}"
            )
        state.evaluation = facts
    return state


def inference(state: GraphState) -> GraphState:
    """Runs the scenario's sample prompts against the base model and scores them.

    Only reaches the tuned model when a deployment already exists — this agent has no tool
    to create one.
    """
    agent: NodeName = "inference"
    with trace_step(agent, as_type="agent", input={"scenario_id": state.scenario_id}):
        state.record_visit(agent)
        if state.dry_run:
            return state
        # Live inference is driven by scripts/run_pipeline.py, which owns results.json.
        # The node exists so the graph terminates on a real node rather than a stub, and
        # deliberately performs no billable call on its own.
    return state
