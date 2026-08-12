"""Per-intent slot models. Field order in `FileAutoClaimSlots` matches `SLOT-DESIGN.md` §1.1's
elicitation priority order, not alphabetical -- that ordering is a conversation-design artifact, not
incidental, and is preserved here so the model's own field order documents it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from .claim import CLAIM_NUMBER_PATTERN, POLICE_REPORT_PATTERN
from .enums import ContactField, EntitlementType, LossType
from .policy import POLICY_NUMBER_PATTERN


class FileAutoClaimSlots(BaseModel):
    """The 11-slot FileAutoClaim intake record (PROBLEM-FRAMING.md, SLOT-DESIGN.md §1)."""

    injuries_present: bool
    policy_number: str = Field(pattern=POLICY_NUMBER_PATTERN)
    insured_vehicle_vin: str = Field(min_length=17, max_length=17)
    loss_datetime: datetime
    loss_location: str
    loss_type: LossType
    damage_description: str
    other_party_involved: bool
    other_party_name: str | None = None
    other_party_insurer: str | None = None
    police_report_filed: bool
    police_report_number: str | None = Field(default=None, pattern=POLICE_REPORT_PATTERN)
    driver_name: str
    relationship_to_insured: str = "Self"

    @model_validator(mode="after")
    def _conditional_police_report_number(self) -> "FileAutoClaimSlots":
        if self.police_report_filed and not self.police_report_number:
            raise ValueError(
                "police_report_number is required when police_report_filed is true (SLOT-DESIGN.md §1.2)"
            )
        return self

    @model_validator(mode="after")
    def _other_party_details_require_involvement(self) -> "FileAutoClaimSlots":
        if not self.other_party_involved and (self.other_party_name or self.other_party_insurer):
            raise ValueError("other_party_name/insurer set but other_party_involved is false")
        return self


class CheckClaimStatusSlots(BaseModel):
    """Either slot suffices (SLOT-DESIGN.md §3)."""

    claim_number: str | None = Field(default=None, pattern=CLAIM_NUMBER_PATTERN)
    policy_number: str | None = Field(default=None, pattern=POLICY_NUMBER_PATTERN)

    @model_validator(mode="after")
    def _one_of_required(self) -> "CheckClaimStatusSlots":
        if not self.claim_number and not self.policy_number:
            raise ValueError("either claim_number or policy_number is required")
        return self


class CoverageQuestionSlots(BaseModel):
    policy_number: str = Field(pattern=POLICY_NUMBER_PATTERN)
    coverage_topic: str


class RentalTowingEntitlementSlots(BaseModel):
    entitlement_type: EntitlementType
    policy_number: str = Field(pattern=POLICY_NUMBER_PATTERN)
    claim_number: str | None = Field(default=None, pattern=CLAIM_NUMBER_PATTERN)


class UpdateContactInfoSlots(BaseModel):
    policy_number: str = Field(pattern=POLICY_NUMBER_PATTERN)
    field: ContactField
    new_value: str
