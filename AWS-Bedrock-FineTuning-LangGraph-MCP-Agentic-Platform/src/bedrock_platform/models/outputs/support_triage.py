from typing import Literal

from pydantic import BaseModel, ConfigDict


class SupportTriageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["Billing", "Bug", "Feature-Request", "Account-Access", "Outage"]
    priority: Literal["P1", "P2", "P3"]
    team: str
