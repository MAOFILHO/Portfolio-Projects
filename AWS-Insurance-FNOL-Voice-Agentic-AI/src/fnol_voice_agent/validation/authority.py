"""Authority limits, per `docs/phase0/DOMAIN-ARTIFACTS.md`'s harvested authority model and
`docs/phase1/PROBLEM-FRAMING.md`'s non-goals: "$0 settlement authority, a $5,000 reserve ceiling, and no
ability to deny a claim." This module is a defensive guard, not a business calculator -- no code path in
this project's design is supposed to reach `assert_within_authority` with a violating action, since the
graph never offers a settle/deny tool at all (Phase 5's MCP servers, Stage 2, deliberately have no such
tool). The guard exists so that if one ever were added by mistake, it fails loudly and immediately rather
than silently executing.
"""

from __future__ import annotations

FNOL_SPECIALIST_SETTLEMENT_AUTHORITY_CAD = 0
FNOL_SPECIALIST_RESERVE_CEILING_CAD = 5_000
FNOL_SPECIALIST_CAN_DENY = False


class AuthorityViolation(Exception):
    """Raised when a code path attempts an action outside this agent's authority."""


def assert_within_authority(action: str, amount_cad: float | None = None) -> None:
    if action in ("settle", "approve_payment"):
        raise AuthorityViolation(
            f"{action!r} attempted with amount_cad={amount_cad!r}; this agent has "
            f"${FNOL_SPECIALIST_SETTLEMENT_AUTHORITY_CAD} settlement authority "
            "(docs/phase1/PROBLEM-FRAMING.md non-goals) and must never execute a payment or settlement."
        )
    if action == "deny":
        raise AuthorityViolation(
            "'deny' attempted; this agent cannot deny a claim (docs/phase0/DOMAIN-ARTIFACTS.md authority matrix)."
        )
    if action == "reserve":
        if amount_cad is None:
            raise AuthorityViolation("'reserve' attempted with no amount_cad specified.")
        if amount_cad > FNOL_SPECIALIST_RESERVE_CEILING_CAD:
            raise AuthorityViolation(
                f"reserve of {amount_cad} exceeds the ${FNOL_SPECIALIST_RESERVE_CEILING_CAD} ceiling."
            )
