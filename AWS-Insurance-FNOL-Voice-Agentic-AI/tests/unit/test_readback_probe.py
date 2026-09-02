"""Tests for `redteam/readback_probe.py` -- `ADR-017` condition part 3. Every AWS-shaped dependency here
is fake (`FakeBedrockConverseClient`, `MockGuardrailClient`), same posture `test_graph_integration.py`
takes for the graph itself: this proves the probe's *own* logic (coverage matching, pass/fail, the two
LLM-based sites' prompt construction) is correct, independent of a real Bedrock/Guardrail resource. The
real client wiring lives in `redteam/run.py:main()` and is exercised only by a real `make redteam` run.
"""

from __future__ import annotations

from typing import Any

import pytest

from fnol_voice_agent.agents.testing.fake_llm import (
    FakeBedrockConverseClient,
    converse_text_response,
)
from fnol_voice_agent.guardrails.client import MockGuardrailClient, MockGuardrailRule
from redteam import readback_probe
from redteam.readback_probe import (
    _probe_check_claim_status,
    _probe_file_auto_claim,
    run_readback_probe,
)
from redteam.response_text_sites import ResponseTextSite


def _clean_caller() -> FakeBedrockConverseClient:
    # Two generate_response calls happen per run (coverage_question, rental_towing) -- queued FIFO.
    return FakeBedrockConverseClient(
        responses=[
            converse_text_response("Towing is covered up to the policy limit."),
            converse_text_response("Rental is covered; 8 days and $400 remain on this claim."),
        ]
    )


# --- The two deterministic, no-AWS probes, tested directly against real node functions -----------------


def test_probe_file_auto_claim_covers_its_four_dynamic_sites_with_real_text() -> None:
    """`D207`/`OI125` direction 3 turned the `insured_vehicle_vin` elicitation prompt (#2) dynamic --
    it was a `_ELICITATION_PROMPTS[next_slot]` literal, now a `Name` (`prompt`) built by
    `_vehicle_choices_prompt` -- a fourth site alongside the pre-existing three."""
    result = _probe_file_auto_claim()
    assert set(result) == {
        "fnol_voice_agent.agents.nodes.file_auto_claim::file_auto_claim#2",
        "fnol_voice_agent.agents.nodes.file_auto_claim::file_auto_claim#3",
        "fnol_voice_agent.agents.nodes.file_auto_claim::file_auto_claim#5",
        "fnol_voice_agent.agents.nodes.file_auto_claim::file_auto_claim#6",
    }
    vehicle_choice = result["fnol_voice_agent.agents.nodes.file_auto_claim::file_auto_claim#2"]
    assert vehicle_choice == "Is this about the 2022 Meridian, or the 2024 Skiff?"
    confirm = result["fnol_voice_agent.agents.nodes.file_auto_claim::file_auto_claim#3"]
    assert "should i go ahead" in confirm.lower()
    except_text = result["fnol_voice_agent.agents.nodes.file_auto_claim::file_auto_claim#5"]
    assert "ran into a problem" in except_text.lower()
    success_text = result["fnol_voice_agent.agents.nodes.file_auto_claim::file_auto_claim#6"]
    assert "your claim number is clm-" in success_text.lower()


def test_probe_check_claim_status_covers_its_one_dynamic_site_with_the_flagship_claim() -> None:
    result = _probe_check_claim_status()
    assert set(result) == {"fnol_voice_agent.agents.nodes.check_claim_status::check_claim_status#5"}
    text = result["fnol_voice_agent.agents.nodes.check_claim_status::check_claim_status#5"]
    assert "clm-2608-00042-4" in text.lower()


# --- End-to-end, with fakes ------------------------------------------------------------------------------


def test_run_readback_probe_passes_with_a_clean_guardrail_and_zero_coverage_gaps() -> None:
    caller = _clean_caller()
    guardrail = MockGuardrailClient()  # no rules -- everything reads action: NONE

    report = run_readback_probe(guardrail, caller)

    assert report.passed
    assert report.coverage_gaps == []
    assert report.unresolved_sources == []
    # 4 (file_auto_claim) + 1 (check_claim_status) + 2 (coverage_question) + 1 (rental_towing) = 8.
    assert len(report.covered) == 8
    assert all(r.guardrail_action == "NONE" for r in report.covered)


def test_run_readback_probe_fails_when_the_guardrail_would_mask_a_probed_site() -> None:
    # Proves the check has teeth: a rule shaped like Bedrock's real PHONE ANONYMIZE, matched against the
    # real-shaped PII fixture the coverage_question/rental_towing probes seed their prompts with. If the
    # generation path ever regressed to echoing it, this is exactly what would catch it.
    caller = _clean_caller()
    guardrail = MockGuardrailClient(
        output_rules=(
            MockGuardrailRule(
                pattern=r"\d{3}-\d{3}-\d{4}",
                reason="pii:PHONE (test stand-in)",
                is_regex=True,
                action="MASK",
            ),
        )
    )
    # Make the fake generation echo the phone number, simulating exactly the regression this probe exists
    # to catch.
    caller = FakeBedrockConverseClient(
        responses=[
            converse_text_response("Sure, I'll follow up at 416-987-1547."),
            converse_text_response("Rental is covered; 8 days and $400 remain on this claim."),
        ]
    )

    report = run_readback_probe(guardrail, caller)

    assert not report.passed
    failing = [r for r in report.covered if not r.passed]
    assert len(failing) == 1
    assert failing[0].site.qualname == "make_coverage_question_node.coverage_question"
    assert failing[0].guardrail_action == "GUARDRAIL_INTERVENED"


def test_run_readback_probe_reports_a_coverage_gap_for_a_site_no_probe_covers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulates the exact drift this whole mechanism exists to catch: a new dynamic site appears (a new
    # branch, or a new node) that no hand-written probe in _SITE_PROBES-equivalent coverage yet exercises.
    real_discover = readback_probe.discover_response_text_sites

    phantom_site = ResponseTextSite(
        module="fnol_voice_agent.agents.nodes.file_auto_claim",
        qualname="file_auto_claim",
        ordinal=99,
        lineno=9999,
        branch_kind="other",
        kind="dynamic",
        snippet="a hypothetical new dynamic branch",
    )

    def _discover_with_phantom(module: Any) -> list[ResponseTextSite]:
        sites = real_discover(module)
        if module.__name__ == "fnol_voice_agent.agents.nodes.file_auto_claim":
            sites = [*sites, phantom_site]
        return sites

    monkeypatch.setattr(readback_probe, "discover_response_text_sites", _discover_with_phantom)

    report = run_readback_probe(MockGuardrailClient(), _clean_caller())

    assert not report.passed
    assert phantom_site in report.coverage_gaps
    # The real, coverable sites are unaffected -- a coverage gap on one site must not swallow the rest.
    assert len(report.covered) == 8
    assert all(r.passed for r in report.covered)
