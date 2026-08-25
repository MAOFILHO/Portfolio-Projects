"""`D140`/`OI58`'s structural check -- fails if any escalation-shaped `response_text` site lacks a real
`EscalationRecord`. Built because reading the defect at one site did not stop it recurring at three more:
`guardrails_nodes.py`'s `check_authority`/`violation` branch (`:64-96`) names `D43` by number as precisely
the mistake it is avoiding, and the very next branch in the same function (`result_gr.blocked`, `:106-107`)
made it anyway. This module re-derives the site inventory from source at check time instead of trusting a
list a human maintains, so a future site of this shape is in scope automatically, not by someone
remembering to add it here.

**Scope, stated plainly, not assumed.** Every module in `agents.nodes` (auto-discovered via
`pkgutil.iter_modules` -- a new file dropped into that package is in scope automatically, no hand
registration needed) plus `agents.graph` itself, named explicitly here because it is the one
node-producing module that lives outside the package (`_guardrail_blocked_response` is defined there) and
there is exactly one such file, so naming it explicitly costs nothing in maintenance. This is deliberately
a DIFFERENT, broader scope than `readback_probe.py`'s `OUTPUT_GUARDRAIL_SOURCES`-anchored one: that
mechanism exists to PII-probe the four non-exception intent nodes specifically, and by design excludes
`update_contact_info`, `guardrails_nodes.py`, and `graph.py` itself. Three of `D140`'s seven known sites
(three originally reported, four more this check itself found while being built -- see `D141`/`OI59`) live
outside that scope, which is why this is a new module, not an extension of `readback_probe.py`.

**What counts as a finding.** A `ResponseTextSite` with `is_escalation_shaped=True` and
`has_escalation_key=False`. Both fields are computed once, in `response_text_sites.py`, from the same AST
walk that already finds every `response_text` site -- see that module's docstring for exactly what each
means, how each is derived, and the keyword heuristic's stated blind spot (a value built through a
function call or attribute lookup whose static source text contains neither keyword would not be
flagged -- none of the current corpus is shaped that way, verified by hand while building this).

**`KNOWN_PENDING_TRIAGE` -- why a finding and a gate failure are not the same thing.** The four sites this
check found while being built are a genuinely different disposition than the three `D140` sites it was
built to catch: each of those three was a *confirmed* promise-with-no-record defect, verified against
`DIALOGUE-POLICIES.md`. The four new ones are *untriaged* -- for at least two of them (both `_ABSTENTION`
branches) "I can't determine that from here" reads as a deflection, not a promise of transfer, and whether
abstention should escalate at all is an open design question, not a bug. Filed separately as `D141`/`OI59`
rather than folded into `D140` (same pattern as `D123`/`D127`: same defect *shape*, different disposition,
cross-referenced not merged) precisely so `D140`/row 9 -- which has no accept-risk escape -- does not stay
open pending four design calls it was never scoped to answer.

That does not mean this check goes quiet about them. A check that reports clean on sites it already found
is worse than no check -- silence reads as "nothing here" rather than "something here, already decided
against". So `KNOWN_PENDING_TRIAGE` holds every currently-untriaged site with a reason citing the open item
tracking it; `passed` only ignores sites that are BOTH found again this run AND listed here with a reason.
Three consequences fall out of that, all deliberate:

1. A listed site still prints every run, under "PENDING TRIAGE", not silently swallowed.
2. A new, unlisted site of this shape -- anywhere in scope, found by anyone, including a future instance of
   exactly this recurrence -- fails the gate. Nothing here is exempted by default; everything exempted is
   exempted by name, with a reason.
3. A listed site that stops being found (because someone fixed it without touching this list) is reported
   as `stale_allowlist_entries`, visibly, so the list cannot silently outlive what it was tracking -- not a
   failure (fixing something is not a regression), but not invisible either.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from fnol_voice_agent.agents import nodes as _nodes_package
from redteam.response_text_sites import ResponseTextSite, discover_response_text_sites

# `D141`/`OI59`: filed, NOT decided, same session `D140`/`OI58` was fixed -- see that entry's module
# docstring paragraph above for why these are a separate item rather than folded into `D140`. Each reason
# names the open item, not just "pending" on its own, so a reader hitting this in five sessions' time has
# somewhere to go rather than a dead label.
KNOWN_PENDING_TRIAGE: dict[str, str] = {
    "fnol_voice_agent.agents.nodes.coverage_question::make_coverage_question_node.coverage_question#3": (
        "triage pending, D141/OI59 -- the PRIMARY site for DIALOGUE-POLICIES.md §8's already"
        "-documented CoverageQuestion eligibility/amount trigger; only the SECONDARY, output-boundary"
        " enforcement (guardrails_nodes.py's check_authority) is wired today. Question: should the"
        " primary site also escalate, or is the secondary catch sufficient by design?"
    ),
    "fnol_voice_agent.agents.nodes.coverage_question::make_coverage_question_node.coverage_question#4": (
        "triage pending, D141/OI59 -- the _ABSTENTION branch. 'I can't determine that from here' reads"
        " as a deflection, not a promise of transfer -- whether abstention should escalate at all is an"
        " open design question, not a confirmed instance of D140's defect."
    ),
    "fnol_voice_agent.agents.nodes.rental_towing::make_rental_towing_node.rental_towing_entitlement#3": (
        "triage pending, D141/OI59 -- same _ABSTENTION shape as coverage_question's sibling site; same"
        " open question, not yet decided whether it applies identically here."
    ),
    "fnol_voice_agent.agents.nodes.file_auto_claim::file_auto_claim#5": (
        "triage pending, D141/OI59 -- the tool-failure except branch (VehicleNotOnPolicyError /"
        " PolicyNotFoundErrorForNewClaim / InvalidNewClaimError), an inline f-string rather than a"
        " module constant. Same except-branch-interpolation shape D123/D127 already covered for a"
        " readback question; this is the same site family asked as an escalation question instead."
    ),
}


def _discover_node_modules() -> list[ModuleType]:
    """Every module in `agents.nodes`, auto-discovered, plus `agents.graph` named explicitly (see module
    docstring's "Scope" note). Sorted by name for a deterministic report order."""
    modules = [
        importlib.import_module(f"{_nodes_package.__name__}.{info.name}")
        for info in pkgutil.iter_modules(_nodes_package.__path__)
    ]
    modules.append(importlib.import_module("fnol_voice_agent.agents.graph"))
    return sorted(modules, key=lambda module: module.__name__)


@dataclass(frozen=True)
class EscalationCoverageReport:
    checked_modules: tuple[str, ...]
    unescalated_sites: tuple[ResponseTextSite, ...]

    @property
    def new_unescalated_sites(self) -> tuple[ResponseTextSite, ...]:
        """The sites that actually fail the gate: found unescalated this run AND not in
        `KNOWN_PENDING_TRIAGE`. A brand-new entry here is `D140`'s defect recurring again, caught by the
        mechanism built to catch it -- not a hypothetical, it happened once already while this was built.
        """
        return tuple(s for s in self.unescalated_sites if s.site_id not in KNOWN_PENDING_TRIAGE)

    @property
    def pending_triage_sites(self) -> tuple[ResponseTextSite, ...]:
        """Found unescalated this run AND allowlisted -- visible every run, never silently green."""
        return tuple(s for s in self.unescalated_sites if s.site_id in KNOWN_PENDING_TRIAGE)

    @property
    def stale_allowlist_entries(self) -> tuple[str, ...]:
        """Allowlisted `site_id`s NOT found unescalated this run -- either fixed (trim the entry) or
        renamed/moved (the AST walker's `site_id` is ordinal-based, so a reordering edit can shift it; see
        `response_text_sites.py`). Not a gate failure -- an improvement is never a regression -- but
        reported so the list cannot quietly outlive what it was tracking."""
        found_ids = {s.site_id for s in self.unescalated_sites}
        return tuple(site_id for site_id in KNOWN_PENDING_TRIAGE if site_id not in found_ids)

    @property
    def passed(self) -> bool:
        return len(self.new_unescalated_sites) == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checked_modules": list(self.checked_modules),
            "new_unescalated_sites": [
                {"site_id": s.site_id, "location": f"{s.module}:{s.lineno}", "snippet": s.snippet}
                for s in self.new_unescalated_sites
            ],
            "pending_triage_sites": [
                {
                    "site_id": s.site_id,
                    "location": f"{s.module}:{s.lineno}",
                    "snippet": s.snippet,
                    "reason": KNOWN_PENDING_TRIAGE[s.site_id],
                }
                for s in self.pending_triage_sites
            ],
            "stale_allowlist_entries": list(self.stale_allowlist_entries),
        }


def check_escalation_coverage() -> EscalationCoverageReport:
    """Runs the check across every in-scope module (see module docstring) and returns every escalation
    -shaped site found with no sibling `escalation` key, in discovery order. An empty `unescalated_sites`
    tuple is the strongest passing state -- there is no separate "nothing to check" outcome, matching this
    project's own `--require-at-least` convention (`scripts/check_flows.py`): `_discover_node_modules`
    always returns at least `agents.graph`, so a config error that silently checked zero modules is not
    possible here the way a glob returning nothing would be. `unescalated_sites` is the raw finding set
    (allowlisted or not) -- `.passed` is what actually gates, via `new_unescalated_sites`.
    """
    modules = _discover_node_modules()
    unescalated: list[ResponseTextSite] = []
    for module in modules:
        for site in discover_response_text_sites(module):
            if site.is_escalation_shaped and not site.has_escalation_key:
                unescalated.append(site)
    return EscalationCoverageReport(
        checked_modules=tuple(module.__name__ for module in modules),
        unescalated_sites=tuple(unescalated),
    )


def render(report: EscalationCoverageReport) -> str:
    lines = [
        "=" * 78,
        f"D140/OI58 ESCALATION COVERAGE CHECK (make redteam) -- {len(report.checked_modules)} modules",
        "=" * 78,
        "",
        f"Overall: {'PASS' if report.passed else '*** FAIL ***'}",
        "",
    ]
    for module_name in report.checked_modules:
        lines.append(f"  scanned: {module_name}")
    lines.append("")
    if report.new_unescalated_sites:
        lines.append(
            "*** NEW / UNLISTED -- promises a transfer with no EscalationRecord, not allowlisted ***"
        )
        for site in report.new_unescalated_sites:
            lines.append(f"    {site.site_id} ({site.module}:{site.lineno}) -- {site.snippet}")
        lines.append("")
    if report.pending_triage_sites:
        lines.append("--- PENDING TRIAGE -- known, allowlisted, does not fail the gate ---")
        for site in report.pending_triage_sites:
            lines.append(f"    {site.site_id} ({site.module}:{site.lineno})")
            lines.append(f"        reason: {KNOWN_PENDING_TRIAGE[site.site_id]}")
        lines.append("")
    if report.stale_allowlist_entries:
        lines.append("--- STALE ALLOWLIST ENTRIES -- listed but not found unescalated this run ---")
        for site_id in report.stale_allowlist_entries:
            lines.append(f"    {site_id}")
        lines.append(
            "    (either fixed -- trim this entry -- or the AST ordinal shifted; check by hand)"
        )
        lines.append("")
    if report.passed and not report.pending_triage_sites and not report.stale_allowlist_entries:
        lines.append("every escalation-shaped response_text site carries a real EscalationRecord.")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    """`make redteam`-callable entry point, same convention as `readback_probe.py`'s own `main`."""
    report = check_escalation_coverage()
    print(render(report))
    if not report.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()


__all__ = [
    "KNOWN_PENDING_TRIAGE",
    "EscalationCoverageReport",
    "check_escalation_coverage",
    "render",
    "main",
]
