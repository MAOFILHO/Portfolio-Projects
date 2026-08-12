from pydantic import BaseModel, ConfigDict


class GardeningOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
