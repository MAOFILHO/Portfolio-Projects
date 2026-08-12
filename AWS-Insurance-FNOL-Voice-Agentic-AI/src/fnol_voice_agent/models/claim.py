"""Claim record schema -- matches `data/synthetic/claims/claims.json` field-for-field."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from .enums import ClaimStatus, KabcoCode
from .policy import POLICY_NUMBER_PATTERN

CLAIM_NUMBER_PATTERN = r"^CLM-\d{2}\d{2}-\d{5}-\d$"
POLICE_REPORT_PATTERN = r"^\d{4}-\d{4}-\d{3}$"


class RentalStatus(BaseModel):
    """Matches endorsements.md's worked example fields exactly (days_used=12 -> days_remaining=8,
    amount_remaining_cad=400). The four usage fields are None together whenever the endorsement wasn't
    elected -- confirmed against every record in data/synthetic/claims/claims.json, not assumed."""

    elected_on_policy: bool
    days_used: int | None = None
    amount_used_cad: int | None = None
    days_remaining: int | None = None
    amount_remaining_cad: int | None = None

    @model_validator(mode="after")
    def _usage_fields_require_election(self) -> "RentalStatus":
        usage_fields = (
            self.days_used,
            self.amount_used_cad,
            self.days_remaining,
            self.amount_remaining_cad,
        )
        if not self.elected_on_policy and any(f is not None for f in usage_fields):
            raise ValueError(
                "usage fields set on a claim where the rental endorsement wasn't elected"
            )
        return self


class Claim(BaseModel):
    claim_number: str = Field(pattern=CLAIM_NUMBER_PATTERN)
    policy_number: str = Field(pattern=POLICY_NUMBER_PATTERN)
    vin: str = Field(min_length=17, max_length=17)
    loss_datetime: str
    loss_location: str
    # A free-text claims-processing label ("DCPD", "Comprehensive - Theft (recovered, damaged)"),
    # distinct from FileAutoClaimSlots.loss_type's fixed caller-facing enum -- the real corpus is
    # descriptive here, not a closed set, confirmed against every record rather than assumed.
    claim_type: str
    # None for Comprehensive-peril claims (theft, vandalism, weather) where fault doesn't apply at all --
    # confirmed against the real corpus, not assumed.
    fault_percentage_insured: int | None = Field(default=None, ge=0, le=100)
    kabco: KabcoCode
    police_report_filed: bool
    police_report_number: str | None = Field(default=None, pattern=POLICE_REPORT_PATTERN)
    # None only for a freshly-filed (REPORTED) claim -- caught while wiring Stage 6's file_new_claim
    # handler: nothing has been assessed yet at the moment of intake, so there is no repair estimate to
    # carry. Every record in the real corpus (all past REPORTED) still has one, confirmed by
    # test_every_real_synthetic_claim_matches_settlement_arithmetic in test_coverage.py.
    repair_estimate_cad: int | None = None
    actual_cash_value_cad: int
    is_total_loss: bool
    deductible_applied_cad: int
    towing_allowance_cad: int
    status: ClaimStatus
    rental: RentalStatus | None = None
    estimated_settlement_cad: int | None = None
    settlement_amount_cad: int | None = None

    @model_validator(mode="after")
    def _settlement_figures_match_status(self) -> "Claim":
        has_estimate = self.estimated_settlement_cad is not None
        has_actual = self.settlement_amount_cad is not None
        if self.status is ClaimStatus.REPORTED:
            # A freshly-filed claim carries neither -- nothing has been assessed yet. Also true of
            # repair_estimate_cad, checked here rather than as a separate rule since both express the
            # same "nothing assessed yet" fact.
            if has_estimate or has_actual or self.repair_estimate_cad is not None:
                raise ValueError(
                    "a REPORTED claim must not yet carry a repair estimate or a settlement figure -- "
                    "nothing has been assessed at intake time"
                )
            return self
        # Past REPORTED: confirmed as an invariant across every record in the real corpus -- an open
        # claim carries an estimate, a settled/closed claim carries an actual amount -- never both,
        # never neither.
        if has_estimate == has_actual:
            raise ValueError(
                "exactly one of estimated_settlement_cad/settlement_amount_cad must be set once a claim "
                f"is past REPORTED status, got estimated={self.estimated_settlement_cad!r} "
                f"actual={self.settlement_amount_cad!r}"
            )
        if self.repair_estimate_cad is None:
            raise ValueError("repair_estimate_cad must be set once a claim is past REPORTED status")
        return self
