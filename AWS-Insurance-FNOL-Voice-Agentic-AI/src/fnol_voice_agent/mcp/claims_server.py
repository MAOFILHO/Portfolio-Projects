"""Claims domain -- `GetClaimStatus`, `GetRentalStatus`, and `FileNewClaim`
(`docs/phase4/DIALOGUE-POLICIES.md` §3, `docs/phase4/SLOT-DESIGN.md` §3; `docs/phase5/BUILD-PLAN.md`
Stage 2, extended in Stage 6 -- see `file_new_claim`'s docstring for why it lives here rather than in
`agents/nodes/`).

Same ADR-012 shape as `policy_server.py`: everything above `main()` is plain, transport-agnostic Python
reading `data/synthetic/claims/claims.json`, returning Stage 1's `Claim`/`RentalStatus` models; nothing
above `main()` imports the `mcp` package. See `policy_server.py`'s module docstring for the full
rationale -- not repeated per-file here.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from pydantic import BaseModel, Field, ValidationError, model_validator

from fnol_voice_agent.models import Claim, ClaimStatus, KabcoCode, LossType, RentalStatus, Vehicle
from fnol_voice_agent.models.claim import CLAIM_NUMBER_PATTERN
from fnol_voice_agent.models.fnol import FileAutoClaimSlots
from fnol_voice_agent.models.policy import POLICY_NUMBER_PATTERN
from fnol_voice_agent.validation.coverage import rental_days_remaining
from fnol_voice_agent.validation.identifiers import compute_claim_number

from ._paths import CLAIMS_PATH, POLICYHOLDERS_PATH, VEHICLES_PATH

# SLOT-DESIGN.md §3 / DIALOGUE-POLICIES.md's "most recent open claim" resolution treats these two
# statuses as closed; every other `ClaimStatus` value counts as open.
_CLOSED_STATUSES = frozenset({ClaimStatus.SETTLED, ClaimStatus.CLOSED})


class ClaimNotFoundError(LookupError):
    """Raised when a lookup key (claim_number, or policy_number's resolved claim) matches no record."""


class NoOpenClaimError(ClaimNotFoundError):
    """Raised when `policy_number` matches a real policy but has no open claim to resolve to
    (`SLOT-DESIGN.md` §3: "policy_number resolves to the most recent open claim"). A distinct subclass
    of `ClaimNotFoundError` because the failure mode is different -- the policy is real, it just has
    nothing open right now -- and a caller may want to react differently (e.g. offer the most recent
    closed claim instead) than to a policy_number that doesn't exist at all.
    """


class InvalidClaimLookupError(ValueError):
    """Raised when neither `claim_number` nor `policy_number` is supplied, or a supplied value doesn't
    match its `docs/phase3/DATA-CONTRACTS.md` format. Closes `docs/phase2/THREAT-MODEL.md`'s "MCP
    argument validation not yet built" residual risk for this tool.
    """


class RentalStatusUnavailableError(LookupError):
    """Raised when a claim exists but carries no rental status at all (defensive -- every real record in
    the synthetic corpus has one, even when the endorsement wasn't elected, but a handler boundary
    shouldn't assume that holds forever)."""


class RentalArithmeticMismatchError(RuntimeError):
    """Raised when the claim's stored `days_remaining`/`amount_remaining_cad` disagree with Stage 1's
    `validation/coverage.rental_days_remaining` recomputed from `days_used` -- a data/logic consistency
    check, not a caller-input error. Should never fire against the real synthetic corpus (verified by
    hand against every rental-bearing record while building this handler); if it ever does, that's a
    real bug in the corpus or in the arithmetic, and it must not be silently swallowed by returning the
    stored (possibly wrong) figure.
    """


class GetClaimStatusArgs(BaseModel):
    """Input schema for `get_claim_status` -- defined once, imported by nothing else (one adapter pair
    per tool)."""

    claim_number: str | None = Field(default=None, pattern=CLAIM_NUMBER_PATTERN)
    policy_number: str | None = Field(default=None, pattern=POLICY_NUMBER_PATTERN)

    @model_validator(mode="after")
    def _at_least_one_key(self) -> "GetClaimStatusArgs":
        if self.claim_number is None and self.policy_number is None:
            raise ValueError("at least one of claim_number/policy_number must be supplied")
        return self


class GetRentalStatusArgs(BaseModel):
    claim_number: str = Field(pattern=CLAIM_NUMBER_PATTERN)


class VehicleNotOnPolicyError(LookupError):
    """Raised when the supplied VIN doesn't belong to the supplied policy_number, per the referential
    integrity check `scripts/validate_synthetic_records.py` already performs on the static corpus --
    applied here to a claim being filed live instead."""


class PolicyNotFoundErrorForNewClaim(LookupError):
    """Raised when `file_new_claim`'s `policy_number` matches no real policyholder. A separate class
    from `policy_server.PolicyNotFoundError`/`contact_server.PolicyNotFoundError` for the same reason
    `contact_server.py` gives its own: this domain owns its own lookup, not a shared one."""


class InvalidNewClaimError(ValueError):
    """Raised when `file_new_claim`'s slot values fail `models.fnol.FileAutoClaimSlots`' validation
    (bad format, missing conditional field, etc.) -- a distinct class from `InvalidClaimLookupError`,
    which is about lookup keys, not the multi-field intake payload this tool validates."""


class InjuryPresentError(ValueError):
    """Raised if `file_new_claim` is ever called with `injuries_present=True`. This tool must never be
    reached on an injury-flagged turn -- `DIALOGUE-POLICIES.md` §5's hard escalation preempts slot-filling
    before a claim would ever be filed -- but this handler does not trust the caller to have enforced
    that; it refuses defensively rather than silently filing a claim with `kabco` fabricated as "no
    injury" against contrary input.
    """


def _load_claims() -> list[Claim]:
    payload = json.loads(CLAIMS_PATH.read_text())
    return [Claim.model_validate(record) for record in payload["claims"]]


def _load_vehicles() -> list[Vehicle]:
    payload = json.loads(VEHICLES_PATH.read_text())
    return [Vehicle.model_validate(record) for record in payload["vehicles"]]


def _load_deductible_for(policy_number: str) -> int:
    """The Section 7 (Loss-or-Damage) deductible is a fixed policy term, known at intake time even
    though the claim's eventual payout isn't -- looked up from the policyholder record rather than
    guessed. Returns 0 for a policyholder with no Section 7 coverage or DCPD-only claims (matching this
    corpus's deductible-free-by-construction DCPD convention, `coverage-logic.md` §1)."""
    payload = json.loads(POLICYHOLDERS_PATH.read_text())
    for record in payload["policyholders"]:
        if record["policy_number"] == policy_number:
            deductible = record.get("loss_or_damage_coverage", {}).get("deductible")
            return int(deductible) if deductible is not None else 0
    return 0


# In-memory store for claims filed through this handler during the current process -- same "no real
# persistence layer yet" posture as contact_server.py's `_store` (Phase 8's job, not this one's). Keyed
# by claim_number so a re-file attempt with the same number (shouldn't happen given the counter below,
# but defensive) is at least detectable rather than silently duplicated.
_filed_claims: dict[str, Claim] = {}
# Per-YYMM sequence counter, per DATA-CONTRACTS.md §1 ("reset to 00001 each month"). Seeded lazily from
# the real corpus's existing max sequence for that month so a freshly-filed claim this process creates
# can never collide with a fixture claim number already in data/synthetic/claims/claims.json.
_sequence_by_month: dict[str, int] = {}


def _next_claim_number(filed_at: datetime) -> str:
    yy, mm = filed_at.year % 100, filed_at.month
    month_key = f"{yy:02d}{mm:02d}"
    if month_key not in _sequence_by_month:
        existing = [c.claim_number for c in _load_claims() if c.claim_number[4:8] == month_key]
        existing_seqs = [int(number[9:14]) for number in existing]
        _sequence_by_month[month_key] = max(existing_seqs, default=0)
    _sequence_by_month[month_key] += 1
    return compute_claim_number(yy, mm, _sequence_by_month[month_key])


def _find_by_claim_number(claims: list[Claim], claim_number: str) -> Claim:
    for claim in claims:
        if claim.claim_number == claim_number:
            return claim
    raise ClaimNotFoundError(f"no claim found for claim_number={claim_number!r}")


def _most_recent_open_claim(claims: list[Claim], policy_number: str) -> Claim:
    candidates = [
        c for c in claims if c.policy_number == policy_number and c.status not in _CLOSED_STATUSES
    ]
    if not candidates:
        raise NoOpenClaimError(f"policy_number={policy_number!r} has no open claim to resolve to")
    return max(candidates, key=lambda c: datetime.fromisoformat(c.loss_datetime))


def get_claim_status(claim_number: str | None = None, policy_number: str | None = None) -> Claim:
    """`claim_number` **or** `policy_number` -- either suffices (`SLOT-DESIGN.md` §3). When only
    `policy_number` is given, resolves to the most recent **open** claim on that policy, disambiguating
    by `loss_datetime` if more than one is open.

    Raises:
        InvalidClaimLookupError: neither key supplied, or a supplied value fails its format.
        ClaimNotFoundError: `claim_number` supplied but matches no record.
        NoOpenClaimError: `policy_number` supplied but resolves to no open claim.
    """
    try:
        args = GetClaimStatusArgs(claim_number=claim_number, policy_number=policy_number)
    except ValidationError as exc:
        raise InvalidClaimLookupError(str(exc)) from exc

    claims = _load_claims()
    if args.claim_number is not None:
        return _find_by_claim_number(claims, args.claim_number)
    assert (
        args.policy_number is not None
    )  # enforced by the args model's _at_least_one_key validator
    return _most_recent_open_claim(claims, args.policy_number)


def get_rental_status(claim_number: str) -> RentalStatus:
    """`endorsements.md`'s rental arithmetic, resolved for one specific claim
    (`DIALOGUE-POLICIES.md` §3 step 2). The corpus already stores `days_remaining`/`amount_remaining_cad`
    precomputed; this handler recomputes both from `days_used` via Stage 1's
    `validation.coverage.rental_days_remaining` and raises if the stored and recomputed figures disagree,
    rather than trusting the stored value unchecked.

    Raises:
        InvalidClaimLookupError: `claim_number` fails the `CLM-YYMM-NNNNN-C` format.
        ClaimNotFoundError: `claim_number` is well-formed but matches no record.
        RentalStatusUnavailableError: the matched claim carries no rental status at all.
        RentalArithmeticMismatchError: the stored and recomputed rental figures disagree.
    """
    try:
        args = GetRentalStatusArgs(claim_number=claim_number)
    except ValidationError as exc:
        raise InvalidClaimLookupError(str(exc)) from exc

    claims = _load_claims()
    claim = _find_by_claim_number(claims, args.claim_number)
    if claim.rental is None:
        raise RentalStatusUnavailableError(
            f"claim {args.claim_number!r} has no rental status recorded"
        )

    rental = claim.rental
    if rental.elected_on_policy and rental.days_used is not None:
        recomputed_days, recomputed_amount = rental_days_remaining(
            rental.days_used, is_total_loss_claim=claim.is_total_loss
        )
        if (
            recomputed_days != rental.days_remaining
            or recomputed_amount != rental.amount_remaining_cad
        ):
            raise RentalArithmeticMismatchError(
                f"stored rental status for {claim.claim_number} (days_remaining={rental.days_remaining}, "
                f"amount_remaining_cad={rental.amount_remaining_cad}) does not match "
                f"validation.coverage.rental_days_remaining's recomputation from days_used="
                f"{rental.days_used} (days_remaining={recomputed_days}, amount_remaining_cad="
                f"{recomputed_amount})"
            )
    return rental


def resolve_vehicle_description(text: str, policy_number: str) -> str | None:
    """Resolves a caller's free-text vehicle description to a VIN, scoped to one policy's own vehicle
    list -- `D207`/`OI125`'s fix, direction 2. Case-insensitive; matches on the vehicle's `model` name
    alone, `make`+`model`, or `year`+`make`+`model` (all three collapse to "the model name appears in
    the text" in practice, since no single policy in the real corpus has two vehicles sharing a model
    name -- make/year only matter to disambiguate a collision if one ever exists). Also passes a real
    17-character VIN straight through if it already belongs to this policy.

    Returns None -- not an exception -- on no match or an ambiguous match (more than one vehicle on the
    policy matches), so the caller's slot stays unanswered and gets re-asked rather than filing a claim
    against the wrong vehicle.
    """
    candidate = text.strip().upper()
    vehicles = [v for v in _load_vehicles() if v.policy_number == policy_number]

    if len(candidate) == 17:
        for vehicle in vehicles:
            if vehicle.vin.upper() == candidate:
                return vehicle.vin

    text_lower = text.lower()
    matches = [v for v in vehicles if re.search(rf"\b{re.escape(v.model.lower())}\b", text_lower)]
    if len(matches) == 1:
        return matches[0].vin
    return None


def file_new_claim(
    policy_number: str,
    insured_vehicle_vin: str,
    loss_datetime: str,
    loss_location: str,
    loss_type: str,
    damage_description: str,
    driver_name: str,
    other_party_involved: bool,
    police_report_filed: bool,
    injuries_present: bool,
    *,
    relationship_to_insured: str = "Self",
    other_party_name: str | None = None,
    other_party_insurer: str | None = None,
    police_report_number: str | None = None,
    filed_at: datetime | None = None,
) -> Claim:
    """`FileAutoClaim`'s close-out write (`SLOT-DESIGN.md` §1.3, `PROBLEM-FRAMING.md`'s success
    criterion: "a claim record written... a speakable claim number read back and confirmed"). Added in
    Stage 6, not Stage 2 -- `docs/phase5/BUILD-PLAN.md`'s original Stage 2 scope named the four
    *read*-and-existing-record tools (`GetPolicyholderElections`, `GetClaimStatus`, `GetRentalStatus`,
    `UpdateContactInfo`) plus the escalation stub; a *new*-claim write tool was a genuine gap only visible
    once Stage 6 needed to close `FileAutoClaim`'s loop. Lives in `claims_server.py`, not a node file, to
    keep "one MCP server per backend domain" intact (`TARGET-LAYOUT.md`) -- this is claims-domain data,
    same as the read handlers above.

    Reuses `models.fnol.FileAutoClaimSlots` for validation rather than re-declaring a parallel schema --
    every one of `SLOT-DESIGN.md` §1's cross-field rules (conditional `police_report_number`, no
    other-party detail without `other_party_involved`) already lives there and applies here unchanged.

    Raises:
        InjuryPresentError: `injuries_present` is True -- this tool must never be reached on an
            injury-flagged turn (see class docstring).
        InvalidNewClaimError (via ValidationError -> re-raised): slot validation failed.
        PolicyNotFoundError / VehicleNotOnPolicyError: `policy_number`/`insured_vehicle_vin` don't
            resolve to a real, matching pair in the synthetic corpus.
    """
    if injuries_present:
        raise InjuryPresentError(
            "file_new_claim called with injuries_present=True -- this must be handled by the injury "
            "escalation path (DIALOGUE-POLICIES.md §5), never filed as an ordinary claim"
        )
    try:
        # FileAutoClaimSlots' fields are typed `datetime`/`LossType`, not `str` -- parsed explicitly here
        # rather than passed through untyped, so a bad value fails as InvalidNewClaimError with a clear
        # message instead of an opaque mypy-invisible pydantic coercion (or a silent runtime TypeError
        # for a value pydantic can't coerce at all).
        slots = FileAutoClaimSlots(
            injuries_present=False,
            policy_number=policy_number,
            insured_vehicle_vin=insured_vehicle_vin,
            loss_datetime=datetime.fromisoformat(loss_datetime),
            loss_location=loss_location,
            loss_type=LossType(loss_type),
            damage_description=damage_description,
            other_party_involved=other_party_involved,
            other_party_name=other_party_name,
            other_party_insurer=other_party_insurer,
            police_report_filed=police_report_filed,
            police_report_number=police_report_number,
            driver_name=driver_name,
            relationship_to_insured=relationship_to_insured,
        )
    except (ValidationError, ValueError) as exc:
        raise InvalidNewClaimError(str(exc)) from exc

    payload = json.loads(POLICYHOLDERS_PATH.read_text())
    if not any(
        record["policy_number"] == slots.policy_number for record in payload["policyholders"]
    ):
        raise PolicyNotFoundErrorForNewClaim(
            f"no policyholder found for policy_number={slots.policy_number!r}"
        )
    vehicle = next((v for v in _load_vehicles() if v.vin == slots.insured_vehicle_vin), None)
    if vehicle is None or vehicle.policy_number != slots.policy_number:
        raise VehicleNotOnPolicyError(
            f"VIN={slots.insured_vehicle_vin!r} is not on policy {slots.policy_number!r}"
        )

    claim_number = _next_claim_number(filed_at or datetime.now(UTC))
    claim = Claim(
        claim_number=claim_number,
        policy_number=slots.policy_number,
        vin=slots.insured_vehicle_vin,
        loss_datetime=slots.loss_datetime.isoformat(),
        loss_location=slots.loss_location,
        claim_type=str(slots.loss_type),
        fault_percentage_insured=None,  # not determined at FNOL time -- coverage-logic.md §2
        kabco=KabcoCode.NO_INJURY,  # guaranteed by the injuries_present=False check above
        police_report_filed=slots.police_report_filed,
        police_report_number=slots.police_report_number,
        repair_estimate_cad=None,  # nothing assessed yet -- see models/claim.py's REPORTED-status rule
        actual_cash_value_cad=vehicle.actual_cash_value_cad,
        is_total_loss=False,  # placeholder pending assessment -- cannot be computed without a repair estimate
        deductible_applied_cad=_load_deductible_for(slots.policy_number),
        towing_allowance_cad=0,  # not yet incurred at intake time
        status=ClaimStatus.REPORTED,
        rental=None,  # not yet relevant -- rental starts once the vehicle reaches a repair facility
        estimated_settlement_cad=None,
        settlement_amount_cad=None,
    )
    _filed_claims[claim_number] = claim
    return claim


def main() -> None:
    """MCP-server adapter: registers all three handlers as tools and serves them over stdio."""
    from mcp.server.mcpserver import MCPServer  # local import -- see policy_server.py's docstring

    server = MCPServer("fnol-claims-server", instructions=__doc__)
    server.add_tool(get_claim_status)
    server.add_tool(get_rental_status)
    server.add_tool(file_new_claim)
    server.run()


if __name__ == "__main__":
    main()
