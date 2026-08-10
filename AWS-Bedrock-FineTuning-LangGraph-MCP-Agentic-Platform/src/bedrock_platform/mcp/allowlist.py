"""Per-agent tool allowlists, enforced at call time.

The project invariant is that no LLM or agent may execute an AWS mutation. That is
enforced twice over:

1. **By omission** — the MCP servers expose no tool that deletes, modifies IAM, edits S3
   lifecycle, creates a deployment, or touches the budget. Those capabilities do not exist
   in the agent's vocabulary at all, so no prompt can reach them.
2. **By allowlist** — each agent may call only the tools it needs. A dataset-prep agent
   that somehow decided to start a training job is refused before the call is dispatched.

Defence in depth matters here because the first layer is a property of code that future
work might extend, while this layer fails closed: a tool absent from every allowlist is
callable by nobody.
"""

from bedrock_platform.mcp.server_bedrock import BEDROCK_TOOLS
from bedrock_platform.mcp.server_dataset import DATASET_TOOLS
from bedrock_platform.mcp.server_eval import EVAL_TOOLS

# Substrings that must never appear in any exposed tool name. Asserted by the unit tests
# against the union of every allowlist, so adding a forbidden tool fails the build.
FORBIDDEN_TOOL_SUBSTRINGS: tuple[str, ...] = (
    "delete",
    "destroy",
    "remove",
    "teardown",
    "iam",
    "role",
    "policy",
    "budget",
    "lifecycle",
    "create_deployment",
    "create_custom_model_deployment",
    "provisioned",
)

ALLOWLIST: dict[str, frozenset[str]] = {
    "dataset_prep": frozenset(DATASET_TOOLS),
    # Deliberately holds the only mutating tool in the system, start_finetune_job, which
    # itself refuses without a human-supplied approval token.
    "finetune_supervisor": frozenset(
        {"start_finetune_job", "get_job_status", "read_training_metrics"}
    ),
    "evaluation": frozenset(EVAL_TOOLS) | {"read_training_metrics"},
    "inference": frozenset({"invoke_base_model", "invoke_tuned_model"}),
}

ALL_TOOLS: frozenset[str] = (
    frozenset(DATASET_TOOLS) | frozenset(BEDROCK_TOOLS) | frozenset(EVAL_TOOLS)
)


class ToolNotAllowedError(PermissionError):
    """Raised when an agent attempts a tool outside its allowlist."""


def assert_tool_allowed(agent: str, tool_name: str) -> None:
    allowed = ALLOWLIST.get(agent)
    if allowed is None:
        raise ToolNotAllowedError(f"Unknown agent {agent!r} — it has no allowlist.")
    if tool_name not in allowed:
        raise ToolNotAllowedError(
            f"Agent {agent!r} may not call {tool_name!r}. Allowed: {', '.join(sorted(allowed))}."
        )


def tools_for(agent: str) -> frozenset[str]:
    return ALLOWLIST.get(agent, frozenset())
