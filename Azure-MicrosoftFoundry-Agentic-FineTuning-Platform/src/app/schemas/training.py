"""Schemas for the supervised fine-tuning training file.

The lab's `travel-finetune-hotel.jsonl` has a rigid shape: every line is one JSON
object with a `messages` array of exactly three messages, in the order
system → user → assistant, and the system message is byte-identical on every row.

We enforce that strictly rather than leniently. Rejected rows are not swallowed —
they surface in the UI as a demonstrated feature.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    """A single message in a training example."""

    model_config = ConfigDict(extra="forbid")

    role: Role
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be blank or whitespace-only")
        return v


class TrainingRecord(BaseModel):
    """One line of the JSONL training file."""

    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def _check_role_order(self) -> TrainingRecord:
        roles = [m.role for m in self.messages]
        if roles != ["system", "user", "assistant"]:
            raise ValueError(f"messages must be exactly [system, user, assistant]; got {roles}")
        return self

    @property
    def system_prompt(self) -> str:
        return self.messages[0].content

    @property
    def user_prompt(self) -> str:
        return self.messages[1].content

    @property
    def assistant_response(self) -> str:
        return self.messages[2].content


class RowError(BaseModel):
    """A rejected line, kept so the UI can show *why* it failed."""

    line_number: int
    error: str
    raw: str = ""


class ValidationReport(BaseModel):
    """Outcome of validating a whole JSONL file."""

    file_name: str
    total_lines: int
    valid_rows: int
    errors: list[RowError] = Field(default_factory=list)
    distinct_system_prompts: int = 0
    size_bytes: int = 0

    @property
    def is_valid(self) -> bool:
        return not self.errors and self.valid_rows > 0

    @property
    def has_consistent_system_prompt(self) -> bool:
        """The lab's dataset teaches one persona, so one system prompt is expected.

        A mixed file is not *invalid* — but it dilutes the behaviour being taught,
        which is worth surfacing rather than hiding.
        """
        return self.distinct_system_prompts == 1


def validate_jsonl_text(text: str, file_name: str = "training.jsonl") -> ValidationReport:
    """Validate raw JSONL text, collecting every failure instead of raising.

    Returns a report; callers decide whether to proceed. This is deliberately
    total: one bad line must not hide the other nine.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    errors: list[RowError] = []
    system_prompts: set[str] = set()
    valid = 0

    for i, line in enumerate(lines, start=1):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(RowError(line_number=i, error=f"invalid JSON: {exc.msg}", raw=line[:200]))
            continue
        try:
            record = TrainingRecord.model_validate(payload)
        except Exception as exc:  # pydantic ValidationError
            first = str(exc).splitlines()
            detail = first[1].strip() if len(first) > 1 else str(exc)
            errors.append(RowError(line_number=i, error=detail, raw=line[:200]))
            continue
        system_prompts.add(record.system_prompt)
        valid += 1

    return ValidationReport(
        file_name=file_name,
        total_lines=len(lines),
        valid_rows=valid,
        errors=errors,
        distinct_system_prompts=len(system_prompts),
        size_bytes=len(text.encode("utf-8")),
    )
