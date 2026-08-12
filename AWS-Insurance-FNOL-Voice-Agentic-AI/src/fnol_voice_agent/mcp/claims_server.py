"""Claims domain -- `GetClaimStatus` and `GetRentalStatus`
(`docs/phase4/DIALOGUE-POLICIES.md` §3, `docs/phase4/SLOT-DESIGN.md` §3; `docs/phase5/BUILD-PLAN.md`
Stage 2).

Same ADR-012 shape as `policy_server.py`: everything above `main()` is plain, transport-agnostic Python
reading `data/synthetic/claims/claims.json`, returning Stage 1's `Claim`/`RentalStatus` models; nothing
above `main()` imports the `mcp` package. See `policy_server.py`'s module docstring for the full
rationale -- not repeated per-file here.
"""

from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, Field, ValidationError, model_validator

from fnol_voice_agent.models import Claim, ClaimStatus, RentalStatus
from fnol_voice_agent.models.claim import CLAIM_NUMBER_PATTERN
from fnol_voice_agent.models.policy import POLICY_NUMBER_PATTERN
from fnol_voice_agent.validation.coverage import rental_days_remaining

from ._paths import CLAIMS_PATH

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


def _load_claims() -> list[Claim]:
    payload = json.loads(CLAIMS_PATH.read_text())
    return [Claim.model_validate(record) for record in payload["claims"]]


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


def main() -> None:
    """MCP-server adapter: registers both handlers as tools and serves them over stdio."""
    from mcp.server.mcpserver import MCPServer  # local import -- see policy_server.py's docstring

    server = MCPServer("fnol-claims-server", instructions=__doc__)
    server.add_tool(get_claim_status)
    server.add_tool(get_rental_status)
    server.run()


if __name__ == "__main__":
    main()
