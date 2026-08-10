from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator


class PatientTriageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department: str
    urgency: Literal["Emergency", "Urgent", "Routine"]
    action: str

    @model_validator(mode="after")
    def emergency_action_required(self) -> Self:
        if self.urgency == "Emergency" and "emergency" not in self.action.lower():
            raise ValueError(
                "for urgency 'Emergency', action must advise contacting emergency services"
            )
        return self
