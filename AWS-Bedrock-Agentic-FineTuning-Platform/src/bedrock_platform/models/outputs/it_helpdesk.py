from pydantic import BaseModel, ConfigDict

L2_ESCALATION_LINE = "If this persists, I'll raise a ticket to L2."


class ItHelpdeskOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
