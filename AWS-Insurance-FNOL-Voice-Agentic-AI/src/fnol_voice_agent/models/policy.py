"""Policyholder record schema -- field-for-field match to `data/synthetic/policyholders/policyholders.json`
so `Policyholder.model_validate(record)` parses the real synthetic corpus directly, with no adapter layer
that could silently drift from the data Phase 3 already shipped and Phase 3's own
`scripts/validate_synthetic_records.py` already validates.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

POLICY_NUMBER_PATTERN = r"^PY\d{4}$"


class AccidentBenefitsElections(BaseModel):
    """The six 2026-07-01 SABS optional elections (ONTARIO-INSURANCE-REFERENCE.md §3). Medical/
    Rehabilitation/Attendant Care are mandatory at every severity track and are not modeled here --
    they don't vary by policyholder, which is exactly why coverage-logic.md §4 answers them from the
    RAG corpus alone, never this record."""

    income_replacement_benefit: bool
    caregiver_benefit: bool
    housekeeping_home_maintenance_benefit: bool
    dependent_care_benefit: bool
    death_funeral_benefits: bool
    indexation_benefit: bool


class DCPDElection(BaseModel):
    opted_out: bool
    has_optional_deductible: bool


class LossOrDamageCoverage(BaseModel):
    """Section 7 (optional). `type` is None for a liability-only policyholder (e.g. PY1103)."""

    type: str | None = None
    deductible: int | None = None


class RentalEndorsement(BaseModel):
    """OPCF-20-modeled rental reimbursement (endorsements.md). All fields None when not elected."""

    elected: bool
    daily_cap: int | None = None
    max_days: int | None = None
    total_cap: int | None = None


class Policyholder(BaseModel):
    policy_number: str = Field(pattern=POLICY_NUMBER_PATTERN)
    first_name: str
    last_name: str
    phone: str
    email: str
    address: str
    drivers_license: str
    policy_effective_date: str
    third_party_liability_limit: int
    accident_benefits_elections: AccidentBenefitsElections
    dcpd: DCPDElection
    loss_or_damage_coverage: LossOrDamageCoverage
    rental_endorsement: RentalEndorsement
    vehicles: list[str]
