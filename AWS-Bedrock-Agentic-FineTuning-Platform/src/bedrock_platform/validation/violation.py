from pydantic import BaseModel, ConfigDict


class SchemaViolation(BaseModel):
    """A caught mismatch between a model's raw output and the scenario's expected schema.

    This is a successful demo outcome, not an error — the UI surfaces it as such.
    """

    model_config = ConfigDict(extra="forbid")

    raw_text: str
    error_path: str
    expected_schema: str
