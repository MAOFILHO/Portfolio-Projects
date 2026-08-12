from typing import Literal

from pydantic import BaseModel, ConfigDict, FilePath


class ValidationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str


class ScenarioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Literal[
        "banking",
        "it_helpdesk",
        "pharma",
        "gardening",
        "support_triage",
        "patient_triage",
        "ecommerce",
    ]
    enabled: bool
    display_name: str
    tagline: str
    industry: str
    dataset_path: FilePath
    system_prompt: str
    output_mode: Literal["prose", "strict_json", "numbered_steps", "short_copy"]
    output_schema_ref: str | None = None
    validation_rules: list[ValidationRule] = []
    sample_prompts: list[str]
    # The customization model ID (with the :128k/:256k context suffix) is what
    # CreateModelCustomizationJob takes, but those IDs are PROVISIONED-only and cannot
    # be passed to Converse. Base-model inference needs a separate, on-demand-invocable
    # ID — usually a cross-region inference profile. Kept as explicit config rather than
    # derived from base_model_id: the transform is not a simple suffix strip (Nova 2 Lite
    # additionally requires the "us." profile prefix), and guessing wrong fails at runtime.
    base_model_id: str
    base_inference_model_id: str
    # Always sent explicitly on Converse. Left unset, Bedrock defaults to the model's
    # maximum and reserves that much quota per call, which throttles the account long
    # before the request volume justifies it.
    max_output_tokens: int = 1024
    epochs: int
    validation_split: float = 0.10
