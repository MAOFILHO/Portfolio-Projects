from pydantic import BaseModel, ConfigDict


class TextBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    content: list[TextBlock]


class ConversationRecord(BaseModel):
    """Bedrock conversation fine-tuning record — see CLAUDE.md 'Shared record schema'."""

    model_config = ConfigDict(extra="forbid")

    schemaVersion: str
    system: list[TextBlock]
    messages: list[ConversationMessage]
