"""LangGraph orchestrator: dataset_prep -> finetune_supervisor -> evaluation -> inference.

The graph is linear by design. Fan-out would let two nodes race for the 4 requests/minute
custom-model-deployment quota, which is account-wide for the base model and cannot be
raised (see docs/COST-ACTUALS.md §4.4).

`--dry-run` is the default. Reaching a billable action requires both `--execute` and a
human-typed approval token; neither can be supplied by an agent.

    python -m bedrock_platform.agents.graph --scenario pharma --dry-run
"""

import argparse
import json
import sys

from langgraph.graph import END, StateGraph

from bedrock_platform.agents.nodes import dataset_prep, evaluation, finetune_supervisor, inference
from bedrock_platform.agents.state import NODE_SEQUENCE, GraphState
from bedrock_platform.aws.finetune_client import APPROVAL_TOKEN
from bedrock_platform.observability.langfuse_setup import (
    flush,
    init_tracing,
    set_output,
    trace_run,
    tracing_status,
)


def build_graph() -> StateGraph[GraphState, None, GraphState, GraphState]:
    graph = StateGraph(GraphState)
    graph.add_node("dataset_prep", dataset_prep)
    graph.add_node("finetune_supervisor", finetune_supervisor)
    graph.add_node("evaluation", evaluation)
    graph.add_node("inference", inference)

    graph.set_entry_point("dataset_prep")
    graph.add_edge("dataset_prep", "finetune_supervisor")
    graph.add_edge("finetune_supervisor", "evaluation")
    graph.add_edge("evaluation", "inference")
    graph.add_edge("inference", END)
    return graph


def run(scenario_id: str, dry_run: bool, approval_token: str | None) -> GraphState:
    init_tracing()
    compiled = build_graph().compile()
    initial = GraphState(scenario_id=scenario_id, dry_run=dry_run, approval_token=approval_token)

    # One trace per pipeline run, with the four agents nested beneath it. The approval
    # token is deliberately not traced — it is a credential, not telemetry.
    with trace_run(
        "run-finetune-pipeline",
        input={"scenario_id": scenario_id, "dry_run": dry_run},
        tags=[f"scenario:{scenario_id}", "dry-run" if dry_run else "execute"],
    ) as root:
        final = compiled.invoke(initial)
        # LangGraph returns the state as a dict; re-validate so what callers get is a
        # typed GraphState and not an untyped mapping.
        state = GraphState.model_validate(final)
        set_output(
            root,
            {
                "visited": state.visited,
                "records": state.dataset.record_count if state.dataset else None,
                "estimated_cost_usd": state.cost.one_time_cost_usd if state.cost else None,
                "job_arn": state.job.job_arn if state.job else None,
                "errors": state.errors,
            },
        )

    flush()
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Permit billable actions. Still requires a typed approval token.",
    )
    args = parser.parse_args()

    dry_run = not args.execute
    approval_token: str | None = None

    if not dry_run:
        typed = input(f"Type '{APPROVAL_TOKEN}' to permit a billable fine-tuning job: ").strip()
        if typed != APPROVAL_TOKEN:
            print("Not approved — aborting before any billable action.", file=sys.stderr)
            sys.exit(1)
        approval_token = typed

    print(f"Planned node sequence: {' -> '.join(NODE_SEQUENCE)}")
    print(f"Tracing: {tracing_status() if tracing_status().enabled else init_tracing()}")
    print(f"Mode: {'DRY RUN — no AWS mutation will be performed' if dry_run else 'EXECUTE'}\n")

    state = run(args.scenario, dry_run=dry_run, approval_token=approval_token)

    print(json.dumps(state.model_dump(), indent=2, default=str))
    if state.errors:
        print(f"\n{len(state.errors)} error(s) recorded.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
