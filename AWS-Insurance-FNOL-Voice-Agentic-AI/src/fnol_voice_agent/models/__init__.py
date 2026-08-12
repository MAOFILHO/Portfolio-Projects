"""Typed schemas for the FNOL agent: policy/vehicle/claim records, per-intent slots, the router's turn
classification, and the event vocabulary. See docs/phase5/BUILD-PLAN.md Stage 1.
"""

from .claim import Claim, RentalStatus
from .enums import (
    ClaimStatus,
    ContactField,
    CoverageQuestionType,
    EntitlementType,
    Intent,
    KabcoCode,
    LossType,
)
from .events import AgentEvent, EventType, SafetyEscalatedEvent
from .fnol import (
    CheckClaimStatusSlots,
    CoverageQuestionSlots,
    FileAutoClaimSlots,
    RentalTowingEntitlementSlots,
    UpdateContactInfoSlots,
)
from .policy import (
    AccidentBenefitsElections,
    DCPDElection,
    LossOrDamageCoverage,
    Policyholder,
    RentalEndorsement,
)
from .routing import TurnClassification
from .vehicle import Vehicle

__all__ = [
    "AccidentBenefitsElections",
    "AgentEvent",
    "CheckClaimStatusSlots",
    "Claim",
    "ClaimStatus",
    "ContactField",
    "CoverageQuestionSlots",
    "CoverageQuestionType",
    "DCPDElection",
    "EntitlementType",
    "EventType",
    "FileAutoClaimSlots",
    "Intent",
    "KabcoCode",
    "LossOrDamageCoverage",
    "LossType",
    "Policyholder",
    "RentalEndorsement",
    "RentalStatus",
    "RentalTowingEntitlementSlots",
    "SafetyEscalatedEvent",
    "TurnClassification",
    "UpdateContactInfoSlots",
    "Vehicle",
]
