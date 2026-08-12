"""Enums shared across models, validation, and the agent graph.

Values are the exact strings used in `data/synthetic/**/*.json` and in `docs/phase4/PROMPT-REGISTRY.md`'s
`classify_turn` tool schema — these are not internal-only labels, they are the wire format other Phase 3/4
artifacts already committed to, so `StrEnum` (not a plain `Enum`) is used throughout: a `StrEnum` member
compares equal to and serializes as its own string value, so `LossType.COLLISION == "Collision"` holds
without a `.value` access anywhere a caller expects a plain string.
"""

from __future__ import annotations

from enum import StrEnum


class Intent(StrEnum):
    """Matches PROMPT-REGISTRY.md §1.1's classify_turn tool schema exactly."""

    FILE_AUTO_CLAIM = "FileAutoClaim"
    CHECK_CLAIM_STATUS = "CheckClaimStatus"
    COVERAGE_QUESTION = "CoverageQuestion"
    RENTAL_TOWING_ENTITLEMENT = "RentalTowingEntitlement"
    UPDATE_CONTACT_INFO = "UpdateContactInfo"
    INJURY_ESCALATION = "InjuryEscalation"
    OUT_OF_SCOPE = "OutOfScope"
    AMBIGUOUS = "Ambiguous"


class LossType(StrEnum):
    """PROBLEM-FRAMING.md's FileAutoClaim `loss_type` slot enum."""

    COLLISION = "Collision"
    COMPREHENSIVE = "Comprehensive"
    THEFT = "Theft"
    VANDALISM = "Vandalism"
    WEATHER = "Weather"
    LIABILITY = "Liability"


class KabcoCode(StrEnum):
    """NHTSA MMUCC scene-severity scale (docs/phase0/DOMAIN-ARTIFACTS.md). Deliberately a distinct axis
    from the SABS clinical severity tracks (coverage-logic.md §3) -- never conflated."""

    K = "K"  # fatal
    A = "A"  # suspected serious
    B = "B"  # possible/minor
    C = "C"  # minor/possible
    NO_INJURY = "O"


class ClaimStatus(StrEnum):
    """Matches data/synthetic/claims/claims.json's `status` field values exactly."""

    REPORTED = "Reported"
    UNDER_REVIEW = "UnderReview"
    REPAIR_IN_PROGRESS = "RepairInProgress"
    SETTLED = "Settled"
    CLOSED = "Closed"


class ContactField(StrEnum):
    """UpdateContactInfo's `field` slot (SLOT-DESIGN.md §2)."""

    PHONE = "phone"
    EMAIL = "email"
    MAILING_ADDRESS = "mailing_address"


class CoverageQuestionType(StrEnum):
    """Matches PROMPT-REGISTRY.md §1.1's classify_turn `coverage_question_type` field and
    DIALOGUE-POLICIES.md §2's question-type split exactly."""

    ELECTION_FACT_MANDATORY = "election_fact_mandatory"
    ELECTION_FACT_OPTIONAL = "election_fact_optional"
    ELIGIBILITY_AMOUNT = "eligibility_amount"
    NOT_APPLICABLE = "not_applicable"


class EntitlementType(StrEnum):
    """RentalTowingEntitlement's `entitlement_type` slot (SLOT-DESIGN.md §3)."""

    RENTAL = "rental"
    TOWING = "towing"
