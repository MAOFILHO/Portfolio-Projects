from pydantic import BaseModel, ConfigDict, field_validator

MAX_WORDS = 45


class EcommerceCopyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str

    @field_validator("text")
    @classmethod
    def word_limit(cls, v: str) -> str:
        word_count = len(v.split())
        if word_count > MAX_WORDS:
            raise ValueError(f"description must be at most {MAX_WORDS} words, got {word_count}")
        return v
