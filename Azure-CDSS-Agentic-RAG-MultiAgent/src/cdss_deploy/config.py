"""Deployment configuration via environment variables and CLI flags."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class DeployConfig(BaseSettings):
    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    # Azure
    azure_subscription_id: str = Field(description="Azure subscription ID")
    azure_location: str = Field(description="Azure region (set AZURE_LOCATION in .env)")
    azure_resource_group: str = Field(description="Resource group name (set AZURE_RESOURCE_GROUP in .env)")
    azure_environment: str = Field(default="dev", description="Environment: dev|staging|prod")

    # Source
    cdss_source_dir: str = Field(
        default="../cdss-agentic-rag",
        description="Path to cdss-agentic-rag source directory (relative or absolute)",
    )

    # PubMed
    cdss_pubmed_api_key: str = Field(default="", description="NCBI PubMed API key")
    cdss_pubmed_email: str = Field(default="", description="PubMed contact email")

    # Optional
    cdss_drugbank_api_key: str = Field(default="", description="DrugBank API key (optional)")

    # Deployment flags
    cdss_skip_auth_setup: bool = Field(default=False)
    cdss_skip_frontend_deploy: bool = Field(default=False)
    cdss_image_build_mode: str = Field(default="local", description="local or acr")
    cdss_openai_network_autofix: bool = Field(default=True)
    cdss_kv_temp_ip_allowlist: bool = Field(default=True)

    @field_validator("azure_environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        if v not in ("dev", "staging", "prod"):
            raise ValueError(f"Environment must be dev, staging, or prod, got: {v}")
        return v

    def resolve_source_dir(self, project_root: Path) -> Path:
        source = Path(self.cdss_source_dir)
        if source.is_absolute():
            return source
        return (project_root / source).resolve()

    @property
    def env_vars_for_scripts(self) -> dict[str, str]:
        return {
            "ENV": self.azure_environment,
            "RG": self.azure_resource_group,
            "LOCATION": self.azure_location,
            "CDSS_PUBMED_API_KEY": self.cdss_pubmed_api_key,
            "CDSS_PUBMED_EMAIL": self.cdss_pubmed_email,
            "CDSS_OPENAI_NETWORK_AUTOFIX": str(self.cdss_openai_network_autofix).lower(),
            "CDSS_KV_TEMP_IP_ALLOWLIST": str(self.cdss_kv_temp_ip_allowlist).lower(),
            "CDSS_IMAGE_BUILD_MODE": self.cdss_image_build_mode,
        }
