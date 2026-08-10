from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator


class PharmaTriageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seriousness: Literal["Serious", "Non-serious"]
    event_category: str
    expedited_reporting: bool

    @model_validator(mode="after")
    def expedited_only_when_serious(self) -> Self:
        if self.expedited_reporting and self.seriousness != "Serious":
            raise ValueError("expedited_reporting may be true only when seriousness is 'Serious'")
        return self
