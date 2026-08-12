"""Single source of truth for configuration.

Everything the app needs comes from the environment (or `.env`). Nothing reads
`os.environ` directly outside this module.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
OUTPUTS_DIR = REPO_ROOT / "outputs"

#: Tag applied to every Azure resource so teardown can find orphans at any suffix.
MANAGED_BY_TAG = "foundry-agentic-platform"

#: The travel-assistant system message. This exact string appears three times in
#: the lab guides — as the base-model instruction, as the fine-tuned-model
#: instruction, and as the ``system`` message on every row of the training file.
#: That identity is what makes the baseline-vs-fine-tuned comparison fair, so it
#: is defined once here and reused everywhere.
TRAVEL_SYSTEM_PROMPT = (
    "You are an AI travel assistant that helps people plan their trips. "
    "Your objective is to offer support for travel-related inquiries, such as "
    "visa requirements, weather forecasts, local attractions, and cultural norms. "
    "You should not provide any hotel, flight, rental car or restaurant "
    "recommendations. Ask engaging questions to help someone plan their trip and "
    "think about what they want to do on their holiday."
)

#: The five prompts the guides use to compare base and fine-tuned models (§9, §11).
CANONICAL_TRAVEL_PROMPTS: tuple[str, ...] = (
    "Where in Rome should I stay?",
    "I'm mostly there for the food. Where should I stay to be within walking "
    "distance of affordable restaurants?",
    "What are some local delicacies I should try?",
    "When is the best time of year to visit in terms of the weather?",
    "What's the best way to get around the city?",
)


class Settings(BaseSettings):
    """Runtime configuration, loaded from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Execution mode ----------------------------------------------------
    demo_mode: Literal["mock", "live"] = "mock"

    # --- Azure -------------------------------------------------------------
    azure_subscription_id: str = ""
    azure_tenant_id: str = ""
    azure_location: str = "eastus2"
    azure_foundry_endpoint: str = ""
    azure_foundry_api_key: str = ""
    azure_foundry_project_name: str = ""
    azure_resource_group: str = ""

    # --- Naming ------------------------------------------------------------
    project_base_name: str = "foundry-travel"

    # --- Model deployments -------------------------------------------------
    model_baseline: str = "gpt-4.1"
    model_baseline_version: str = "2025-04-14"
    model_compare_a: str = "gpt-5.4"
    model_compare_a_version: str = "2026-03-05"
    model_compare_b: str = "gpt-5.4-mini"
    model_compare_b_version: str = "2026-03-17"

    # --- Fine-tuning -------------------------------------------------------
    ft_suffix: str = "ft-travel"
    ft_deployment_type: Literal["Developer", "GlobalStandard", "Standard"] = "Developer"
    ft_training_type: Literal["Developer", "Global", "Regional"] = "Developer"

    # The guides never show hyperparameters (they are left at API defaults), so
    # we pin them explicitly for reproducibility. See PLAN.md contradiction #6.
    ft_n_epochs: int = 2
    ft_batch_size: int = 1
    ft_learning_rate_multiplier: float = 1.0
    ft_seed: int = 42

    # --- Evaluation --------------------------------------------------------
    eval_row_count: int = 45
    include_agent_evaluators: bool = True

    # --- Cost guard --------------------------------------------------------
    budget_ceiling_usd: float = 25.0
    budget_alert_email: str = ""

    # --- Observability -----------------------------------------------------
    applicationinsights_connection_string: str = ""
    otel_service_name: str = "foundry-agentic-platform"
    otel_console_export: bool = True

    # --- API / frontend ----------------------------------------------------
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    # --- Static demo auth (a demo gate, NOT real authentication) -----------
    demo_username: str = "demo"
    demo_password: str = "demo123"

    # --- Entra ID bearer-token auth (the public hosted deployment only) ----
    # Blank in local/mock dev — require_entra_auth() (see auth_entra.py)
    # becomes a no-op when these are unset, matching the frontend's
    # isEntraEnabled gate. Set by Container Apps env vars in hosting.tf.
    entra_tenant_id: str = ""
    entra_client_id: str = ""

    @field_validator("azure_location")
    @classmethod
    def _normalise_location(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "")

    @property
    def is_mock(self) -> bool:
        """True when no Azure call may be made and nothing may be billed."""
        return self.demo_mode == "mock"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def compare_models(self) -> tuple[str, str]:
        return (self.model_compare_a, self.model_compare_b)

    def require_live_credentials(self) -> None:
        """Fail fast, with a specific message, when live mode is under-configured."""
        if self.is_mock:
            return
        missing = [
            name
            for name, value in (
                ("AZURE_SUBSCRIPTION_ID", self.azure_subscription_id),
                ("AZURE_FOUNDRY_ENDPOINT", self.azure_foundry_endpoint),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"DEMO_MODE=live requires {', '.join(missing)}. "
                "Run `make provision` first, or set DEMO_MODE=mock to run at zero cost."
            )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
