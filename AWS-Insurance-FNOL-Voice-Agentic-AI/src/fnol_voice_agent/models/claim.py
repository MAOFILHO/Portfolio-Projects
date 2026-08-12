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
    repair_estimate_cad: int
    actual_cash_value_cad: int
    is_total_loss: bool
    deductible_applied_cad: int
    towing_allowance_cad: int
    status: ClaimStatus
    rental: RentalStatus | None = None
    estimated_settlement_cad: int | None = None
    settlement_amount_cad: int | None = None

    @model_validator(mode="after")
    def _exactly_one_settlement_figure(self) -> "Claim":
        # Confirmed as an invariant across every record in the real corpus: an open claim carries an
        # estimate, a settled/closed claim carries an actual amount -- never both, never neither.
        has_estimate = self.estimated_settlement_cad is not None
        has_actual = self.settlement_amount_cad is not None
        if has_estimate == has_actual:
            raise ValueError(
                "exactly one of estimated_settlement_cad/settlement_amount_cad must be set, "
                f"got estimated={self.estimated_settlement_cad!r} actual={self.settlement_amount_cad!r}"
            )
        return self
