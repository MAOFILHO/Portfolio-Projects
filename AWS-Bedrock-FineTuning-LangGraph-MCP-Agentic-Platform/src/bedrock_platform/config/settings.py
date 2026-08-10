from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="forbid")

    aws_region: str = "us-east-1"
    aws_profile: str | None = None
    project_suffix: str

    budget_limit_usd: float
    budget_alert_email: str

    langfuse_host: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    # Lifecycle stage, not a deployment name — Langfuse uses it to keep demo traces out of
    # production dashboards and evaluations.
    langfuse_environment: str = "development"

    otel_exporter_otlp_endpoint: str | None = None

    api_port: int = 8000
    frontend_port: int = 5173
