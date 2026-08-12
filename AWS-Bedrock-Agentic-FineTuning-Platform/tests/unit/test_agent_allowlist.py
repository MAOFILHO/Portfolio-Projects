import pytest

from bedrock_platform.agents.nodes import TOOL_REGISTRY, call_tool
from bedrock_platform.agents.state import NODE_SEQUENCE
from bedrock_platform.mcp.allowlist import (
    ALL_TOOLS,
    ALLOWLIST,
    FORBIDDEN_TOOL_SUBSTRINGS,
    ToolNotAllowedError,
    assert_tool_allowed,
)
from bedrock_platform.mcp.server_bedrock import (
    ApprovalRequiredError,
    StartFinetuneInput,
    start_finetune_job,
)


def test_every_agent_in_the_graph_has_an_allowlist() -> None:
    assert set(ALLOWLIST) == set(NODE_SEQUENCE)


def test_each_agent_can_call_only_its_own_tools() -> None:
    for agent, allowed in ALLOWLIST.items():
        for tool in allowed:
            assert_tool_allowed(agent, tool)
        for tool in ALL_TOOLS - allowed:
            with pytest.raises(ToolNotAllowedError):
                assert_tool_allowed(agent, tool)


def test_unknown_agent_is_refused() -> None:
    with pytest.raises(ToolNotAllowedError):
        assert_tool_allowed("not_an_agent", "validate_dataset")


def test_no_agent_can_reach_a_destructive_or_privileged_tool() -> None:
    """The primary invariant: no LLM or agent may execute an AWS mutation beyond the one
    gated fine-tune launch. Enforced by omission — such tools must not exist at all."""
    for tool in ALL_TOOLS:
        lowered = tool.lower()
        for forbidden in FORBIDDEN_TOOL_SUBSTRINGS:
            assert forbidden not in lowered, f"tool {tool!r} contains forbidden term {forbidden!r}"


def test_only_one_mutating_tool_exists_and_only_one_agent_holds_it() -> None:
    holders = [agent for agent, tools in ALLOWLIST.items() if "start_finetune_job" in tools]
    assert holders == ["finetune_supervisor"]


def test_evaluation_agent_cannot_invoke_models() -> None:
    """Scoring and generating are separated so a scorer cannot spend inference budget."""
    for tool in ("invoke_base_model", "invoke_tuned_model", "start_finetune_job"):
        with pytest.raises(ToolNotAllowedError):
            assert_tool_allowed("evaluation", tool)


def test_dataset_agent_cannot_start_a_job() -> None:
    with pytest.raises(ToolNotAllowedError):
        assert_tool_allowed("dataset_prep", "start_finetune_job")


def test_every_allowlisted_tool_is_registered() -> None:
    """An allowlisted-but-unregistered tool would fail at call time instead of import."""
    for allowed in ALLOWLIST.values():
        for tool in allowed:
            assert tool in TOOL_REGISTRY, f"{tool!r} is allowlisted but not in TOOL_REGISTRY"


def test_registry_exposes_nothing_outside_the_declared_tools() -> None:
    assert set(TOOL_REGISTRY) == set(ALL_TOOLS)


def test_call_tool_enforces_the_allowlist_before_dispatch() -> None:
    """call_tool is the single dispatch point; the check must precede the tool running."""
    with pytest.raises(ToolNotAllowedError):
        call_tool("dataset_prep", "start_finetune_job", StartFinetuneInput(scenario_id="pharma"))


def test_start_finetune_job_refuses_without_an_approval_token() -> None:
    with pytest.raises(ApprovalRequiredError):
        start_finetune_job(
            StartFinetuneInput(scenario_id="pharma", approval_token=None, dry_run=False)
        )


def test_start_finetune_job_refuses_a_wrong_token() -> None:
    for bad in ("approve", "yes", "Approve", "APPROVED", ""):
        with pytest.raises(ApprovalRequiredError):
            start_finetune_job(
                StartFinetuneInput(scenario_id="pharma", approval_token=bad, dry_run=False)
            )


def test_dry_run_returns_a_plan_and_never_a_job() -> None:
    result = start_finetune_job(
        StartFinetuneInput(scenario_id="pharma", approval_token="APPROVE", dry_run=True)
    )
    assert result.job_arn is None
    assert result.dry_run is True
    assert result.planned_job_name
