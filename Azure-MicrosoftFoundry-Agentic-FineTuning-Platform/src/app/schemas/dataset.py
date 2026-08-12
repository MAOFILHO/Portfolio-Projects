"""The selectable fine-tuning dataset catalog.

`travel-finetune-hotel.jsonl` is the lab's own dataset and stays the default
everywhere. The other seven were supplied later as AWS Bedrock Converse-format
JSONL and converted 1:1 to Azure's flat fine-tuning shape by
`data/convert_bedrock_datasets.py` — see that script's docstring for the exact
reshape. They live in `data/converted/` and are additive: nothing about the
lab's own dataset or default behaviour changes because they exist.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DatasetInfo(BaseModel):
    """One entry in the selectable-dataset catalog."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    domain: str
    description: str
    file_name: str
    subdir: str = ""  # "" for data/, "converted" for data/converted/
    source: str = "Azure OpenAI fine-tuning format (native)"


#: Ordered so the lab's own dataset is always first / the default.
DATASET_REGISTRY: tuple[DatasetInfo, ...] = (
    DatasetInfo(
        id="travel-finetune-hotel",
        label="Travel Assistant (lab default)",
        domain="Travel",
        description=(
            "The K21Academy/Microsoft Learn lab's own dataset — a travel assistant "
            "taught to avoid hotel/flight/car/restaurant recommendations and end "
            "with an engaging question. Every other part of this project (Demo 3's "
            "canonical prompts, behavioural checks, cost figures) is grounded in "
            "this specific dataset."
        ),
        file_name="travel-finetune-hotel.jsonl",
        subdir="",
        source="Azure OpenAI fine-tuning format (native)",
    ),
    DatasetInfo(
        id="support-ticket-triage",
        label="Support Ticket Triage",
        domain="Customer Support",
        description="Classifies a support ticket into JSON: category, priority, team.",
        file_name="support_ticket_triage.jsonl",
        subdir="converted",
    ),
    DatasetInfo(
        id="pharma-adverse-event-triage",
        label="Pharmacovigilance Adverse-Event Triage",
        domain="Healthcare / Pharma",
        description=(
            "Classifies an adverse-event case report into JSON: "
            "seriousness, category, expedited reporting."
        ),
        file_name="pharma_adverse_event_triage.jsonl",
        subdir="converted",
    ),
    DatasetInfo(
        id="patient-message-triage",
        label="Patient Message Triage",
        domain="Healthcare / Clinic",
        description=(
            "Routes a clinic patient message to a department with urgency "
            "and next action — never diagnoses."
        ),
        file_name="patient_message_triage.jsonl",
        subdir="converted",
    ),
    DatasetInfo(
        id="ecommerce-product-copy",
        label="E-commerce Product Copy",
        domain="Retail / Marketing",
        description="Turns raw product attributes into a short, benefit-led marketing description.",
        file_name="ecommerce_product_copy.jsonl",
        subdir="converted",
    ),
    DatasetInfo(
        id="it-helpdesk-l1",
        label="IT Helpdesk L1",
        domain="Internal IT",
        description=(
            "Gives numbered troubleshooting steps for common IT issues, "
            "always offering an L2 escalation."
        ),
        file_name="it_helpdesk_l1.jsonl",
        subdir="converted",
    ),
    DatasetInfo(
        id="banking-assistant",
        label="Banking Assistant",
        domain="Financial Services",
        description=(
            "A bank virtual assistant with compliance guardrails (no investment/tax/legal advice)."
        ),
        file_name="banking_assistant.jsonl",
        subdir="converted",
    ),
    DatasetInfo(
        id="gardening-lessons",
        label="Gardening Tutor",
        domain="Education / Lifestyle",
        description="A fun, analogy-driven gardening tutor that flags common mistakes.",
        file_name="gardening_lessons.jsonl",
        subdir="converted",
    ),
)

_BY_ID = {d.id: d for d in DATASET_REGISTRY}


def get_dataset(dataset_id: str) -> DatasetInfo:
    if dataset_id not in _BY_ID:
        raise KeyError(f"unknown dataset id: {dataset_id!r}")
    return _BY_ID[dataset_id]


def dataset_relative_path(dataset_id: str) -> str:
    """Path relative to DATA_DIR, as consumed by the finetune MCP server's
    `path` parameter (which searches DATA_DIR for a given filename)."""
    info = get_dataset(dataset_id)
    return f"{info.subdir}/{info.file_name}" if info.subdir else info.file_name
