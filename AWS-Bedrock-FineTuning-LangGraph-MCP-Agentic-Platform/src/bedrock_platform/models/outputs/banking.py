from pydantic import BaseModel, ConfigDict

TRANSFER_DISCLAIMER = "Transfers may take 1–3 business days."


class BankingAssistantOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
