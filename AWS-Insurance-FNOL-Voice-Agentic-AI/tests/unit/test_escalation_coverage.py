"""`D140`/`OI58`'s structural check (`redteam/escalation_coverage.py`). Two properties, kept separate:

1. Every site fixed THIS session (`agents/graph.py`, `agents/nodes/guardrails_nodes.py`,
   `agents/nodes/update_contact_info.py`) must stay fixed -- a real regression test, not a residual list.
2. This check, built to catch a recurring defect, found the defect recurring a second time WHILE being
   built: four more sites (`coverage_question.py` x2, `rental_towing.py`, `file_auto_claim.py`) are
   escalation-shaped with no `EscalationRecord`, discovered by this exact mechanism, not hand-swept. Filed
   separately as `D141`/`OI59` (not folded into `D140` -- same shape, different disposition, same pattern
   as `D123`/`D127`) because each needs a triage call ("is this a promise of transfer, or a correct
   deflection?") that this session does not make. `KNOWN_PENDING_TRIAGE` (the actual allowlist, with a
   reason per entry) lives in `escalation_coverage.py` itself, not duplicated here -- this test imports it
   as the single source of truth, so the two cannot drift apart.
"""

from __future__ import annotations

from redteam.escalation_coverage import KNOWN_PENDING_TRIAGE, check_escalation_coverage


def test_the_three_d140_sites_fixed_this_session_stay_fixed() -> None:
    """The narrow regression test: none of the three sites this session's GREEN step fixed
    (`graph.py`'s `_guardrail_blocked_response`, `guardrails_nodes.py`'s OUTPUT-block branch,
    `update_contact_info.py`'s confirm-ceiling branch) may reappear in the unescalated set -- allowlisted
    or not. A fixed site belongs in neither `new_unescalated_sites` nor `pending_triage_sites`."""
    report = check_escalation_coverage()
    unescalated_ids = {site.site_id for site in report.unescalated_sites}

    fixed_this_session = {
        "fnol_voice_agent.agents.graph::_guardrail_blocked_response#1",
        "fnol_voice_agent.agents.nodes.guardrails_nodes::make_guardrails_output_node."
        "guardrails_output_check#2",
        "fnol_voice_agent.agents.nodes.update_contact_info::update_contact_info_node#4",
    }
    assert unescalated_ids.isdisjoint(fixed_this_session)


def test_the_known_residual_is_exactly_and_only_the_four_reported_sites() -> None:
    """The broader property, and the one that actually keeps this check honest over time: the full
    unescalated set (allowlisted or not) must equal `KNOWN_PENDING_TRIAGE`'s keys exactly. A regression in
    either direction is a real signal -- a site vanishing from this set with no matching edit to
    `escalation_coverage.py` means the allowlist is stale (probably: someone fixed it and should trim the
    entry -- `stale_allowlist_entries` reports this without failing); a new, unlisted site appearing means
    a fifth instance of `D140`'s class was just introduced, which `new_unescalated_sites` -- and the gate
    this session wires into `make redteam` -- catches."""
    report = check_escalation_coverage()
    unescalated_ids = {site.site_id for site in report.unescalated_sites}

    assert unescalated_ids == set(KNOWN_PENDING_TRIAGE)


def test_the_check_passes_because_every_current_finding_is_allowlisted_with_a_reason() -> None:
    """`D141`/`OI59`'s whole point: untriaged is not the same as unreported. The gate passes today only
    because all four current findings are named in `KNOWN_PENDING_TRIAGE` with a reason citing the open
    item -- not because there is nothing to see. `pending_triage_sites` is where that visibility lives;
    `new_unescalated_sites` (what actually fails the gate) must be empty, and `stale_allowlist_entries`
    must also be empty (every allowlisted site is still genuinely found, not stale bookkeeping)."""
    report = check_escalation_coverage()

    assert report.passed is True
    assert report.new_unescalated_sites == ()
    assert report.stale_allowlist_entries == ()
    assert {site.site_id for site in report.pending_triage_sites} == set(KNOWN_PENDING_TRIAGE)


def test_every_agents_node_module_plus_graph_is_in_scope() -> None:
    """Scope sanity check, not a content assertion: `_discover_node_modules`' `pkgutil` auto-discovery
    must still find every module known to exist in `agents/nodes/` today, plus `agents.graph` itself --
    catches a scope collapse (e.g. an import error silently shrinking the discovered set) independent of
    whatever the escalation-shape findings happen to be."""
    report = check_escalation_coverage()

    assert "fnol_voice_agent.agents.graph" in report.checked_modules
    for expected in (
        "check_claim_status",
        "coverage_question",
        "file_auto_claim",
        "guardrails_nodes",
        "injury_escalation",
        "rental_towing",
        "repair",
        "routing",
        "safety",
        "update_contact_info",
    ):
        assert f"fnol_voice_agent.agents.nodes.{expected}" in report.checked_modules
