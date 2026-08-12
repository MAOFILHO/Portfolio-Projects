from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator


class PharmaTriageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seriousness: Literal["Serious", "Non-serious"]
    # Constrained rather than a bare `str`. The 8 System Organ Class terms below are the
    # only values appearing across all 210 training records, and downstream systems treat
    # the field as an enum — so a near-miss like "Neurological" or "Cardiovascular" is a
    # parse failure, not a partially-correct answer. Left open, the schema guard reported
    # "valid" for output the real contract would reject, making the strict-JSON demo
    # weaker than the contract it claims to enforce.
    event_category: Literal[
        "Cardiac",
        "Gastrointestinal",
        "General",
        "Hepatobiliary",
        "Immune system",
        "Nervous system",
        "Respiratory",
        "Skin",
    ]
    expedited_reporting: bool

    @model_validator(mode="after")
    def expedited_only_when_serious(self) -> Self:
        if self.expedited_reporting and self.seriousness != "Serious":
            raise ValueError("expedited_reporting may be true only when seriousness is 'Serious'")
        return self
