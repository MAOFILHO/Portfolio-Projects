"""The ablation ladder's own validity — `scripts/run_ablation_ladder.py`, Stage 4.

The ladder produces the numbers that decide `ADR-014`'s open question, so the ways it can be wrong are
worth more attention than the ways a normal script can be wrong. Two of them are silent:

* **Rung B stops being an ablation** if the schema surgery no-ops. B would then be a duplicate of A, the
  B−A delta would be noise reported as a finding, and nothing would look broken.
* **Rung D trades recall for precision** if its revised prompt drops the recall bias. That is the one
  trade `C1` forbids outright, and it would show up as a beautiful false-escalation number.

Both are checked here rather than trusted.
"""

from __future__ import annotations

from typing import Any

import pytest

from fnol_voice_agent.aws.bedrock_router import build_classify_turn_tool_spec
from fnol_voice_agent.models.enums import Intent
from scripts.run_ablation_ladder import (
    _REVISED_DETECTOR_PROMPT,
    RUNGS,
    _build_no_injury_tool_spec,
)


def _intent_enum(spec: dict[str, Any]) -> list[str]:
    for definition in spec["toolSpec"]["inputSchema"]["json"]["$defs"].values():
        if "enum" in definition and Intent.COVERAGE_QUESTION.value in definition["enum"]:
            return list(definition["enum"])
    raise AssertionError("no intent enum found in the tool spec")


# --- Rung B is a real ablation --------------------------------------------------------------------


def test_rung_b_removes_injury_escalation_from_the_enum() -> None:
    assert Intent.INJURY_ESCALATION.value in _intent_enum(build_classify_turn_tool_spec())
    assert Intent.INJURY_ESCALATION.value not in _intent_enum(_build_no_injury_tool_spec())


def test_rung_b_changes_nothing_else_about_the_schema() -> None:
    """B−A must attribute to the label space and nothing else. One stray difference and the delta
    measures two changes at once."""
    baseline = _intent_enum(build_classify_turn_tool_spec())
    rung_b = _intent_enum(_build_no_injury_tool_spec())
    assert rung_b == [v for v in baseline if v != Intent.INJURY_ESCALATION.value]

    spec_a, spec_b = build_classify_turn_tool_spec(), _build_no_injury_tool_spec()
    assert spec_a["toolSpec"]["name"] == spec_b["toolSpec"]["name"]
    schema_a = spec_a["toolSpec"]["inputSchema"]["json"]
    schema_b = spec_b["toolSpec"]["inputSchema"]["json"]
    assert schema_a["properties"] == schema_b["properties"]
    assert schema_a.get("required") == schema_b.get("required")


def test_rung_b_does_not_mutate_the_shipped_spec() -> None:
    """`build_classify_turn_tool_spec()` returns a fresh dict each call, but if that ever changed to a
    cached constant, the surgery would corrupt production's schema and the ladder would be measuring
    rung B four times."""
    _build_no_injury_tool_spec()
    assert Intent.INJURY_ESCALATION.value in _intent_enum(build_classify_turn_tool_spec())


def test_rung_b_fails_loudly_if_the_schema_shape_moves(monkeypatch: Any) -> None:
    """A schema-shape change must break the run, not silently produce rung A twice."""
    import scripts.run_ablation_ladder as ladder

    monkeypatch.setattr(
        ladder,
        "build_classify_turn_tool_spec",
        lambda: {"toolSpec": {"name": "classify_turn", "inputSchema": {"json": {}}}},
    )
    with pytest.raises(RuntimeError, match="meaningless B-A delta"):
        ladder._build_no_injury_tool_spec()


# --- Rung D does not trade away recall ------------------------------------------------------------


def test_the_revised_detector_prompt_keeps_the_recall_bias() -> None:
    """`C1` is not tradeable: *"Any configuration that reduces it is rejected regardless of what it
    buys."* A revised prompt that quietly drops "when in doubt, true" would buy false-escalation
    improvements with recall, which is the one purchase this phase may not make."""
    assert "when in doubt" in _REVISED_DETECTOR_PROMPT.lower()


def test_the_revised_detector_prompt_only_adds_the_measured_distinctions() -> None:
    """Rung D is capped at 3 revisions and this is revision 1. Its edit is narrow on purpose: the two
    false-positive shapes the Phase 6 error analysis actually found (vehicle damage in human terms,
    a bare mention that a collision occurred), not a rewrite."""
    lowered = _REVISED_DETECTOR_PROMPT.lower()
    assert "vehicle" in lowered
    assert "a person" in lowered
    # Still a single-purpose detector: no intent classification has crept in.
    assert "intent" in lowered and "you do not classify" in lowered


def test_the_ladder_is_cumulative_and_ordered() -> None:
    """Each rung adds one change to the previous one, which is what makes pairwise deltas
    attributable. Order matters for the same reason."""
    assert [name for name, _description, _run in RUNGS] == ["A", "B", "C", "D"]
