"""Event vocabulary -- refactored from repo 6's 14-event catalog (`docs/phase0/TARGET-LAYOUT.md`), cut down
to the events this project's own six intents and escalation path actually produce. Consumed by Stage 7's
post-call pipeline (`ADR-006`) and the observability trace, not emitted anywhere in Stage 1-5's scope.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from .enums import Intent, KabcoCode


class EventType(StrEnum):
    CLAIM_FILED = "ClaimFiled"
    CLAIM_STATUS_CHECKED = "ClaimStatusChecked"
    COVERAGE_QUESTION_ANSWERED = "CoverageQuestionAnswered"
    RENTAL_TOWING_CHECKED = "RentalTowingChecked"
    CONTACT_UPDATED = "ContactUpdated"
    SAFETY_ESCALATED = "SafetyEscalated"
    CALLER_REQUESTED_AGENT = "CallerRequestedAgent"
    CAPABILITY_ESCALATED = "CapabilityEscalated"
    RETRY_CEILING_REACHED = "RetryCeilingReached"


class AgentEvent(BaseModel):
    """Base envelope every event shares. `contact_id` is the Connect contact ID -- the same key the
    DynamoDB checkpointer (ADR-005) uses, so a trace can always be joined back to conversation state.
    """

    event_type: EventType
    contact_id: str
    occurred_at: datetime
    intent: Intent | None = None


class SafetyEscalatedEvent(AgentEvent):
    event_type: EventType = EventType.SAFETY_ESCALATED
    triggering_layer: str  # "L1" | "L2" | "L3" -- DIALOGUE-POLICIES.md §5
    kabco: KabcoCode | None = None
