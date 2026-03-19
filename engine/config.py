"""
Ironpass — Configuration loaded from environment variables.

All configuration is centralized here. No other module reads env vars directly.
Uses pydantic-settings for validation and type coercion.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import AliasChoices, Field


class Settings(BaseSettings):
    """
    All Ironpass configuration.
    Required fields have no default — the app will not start without them.
    """

    # -----------------------------------------------------------------------
    # Database
    # -----------------------------------------------------------------------
    database_url: str = Field(
        ...,
        description="PostgreSQL connection string",
    )

    # -----------------------------------------------------------------------
    # Redis
    # -----------------------------------------------------------------------
    redis_url: str = Field(
        ...,
        description="Redis connection string",
    )

    # -----------------------------------------------------------------------
    # Security Keys
    # -----------------------------------------------------------------------
    audit_hmac_key: str = Field(
        ...,
        description="64 hex chars — HMAC-SHA256 secret for audit chain signing",
    )
    pseudonym_secret_key: str = Field(
        ...,
        description="64 hex chars — secret for deterministic pseudonym generation",
    )
    proxy_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("IRONPASS_PROXY_API_KEY", "PROXY_API_KEY"),
        description="Exact bearer token required to access Ironpass proxy endpoints",
    )
    dashboard_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "IRONPASS_DASHBOARD_API_KEY",
            "DASHBOARD_API_KEY",
        ),
        description="Exact bearer token required to access dashboard endpoints",
    )

    # -----------------------------------------------------------------------
    # Key Management
    # -----------------------------------------------------------------------
    key_backend: str = Field(
        default="local",
        description='Key backend: "hashicorp", "aws_kms", or "local" (dev only)',
    )

    # HashiCorp Vault (optional — required if key_backend=hashicorp)
    hashicorp_vault_url: str | None = Field(
        default=None,
        description="HashiCorp Vault URL",
    )

    # -----------------------------------------------------------------------
    # Ruleset Engine
    # -----------------------------------------------------------------------
    ruleset_priority: list[str] = Field(
        default=["pci_dss", "hipaa", "gdpr", "soc2"],
        description="Priority order for ruleset tie-breakers.",
    )
    hashicorp_vault_token: str | None = Field(
        default=None,
        description="HashiCorp Vault access token",
    )

    # AWS KMS (optional — required if key_backend=aws_kms)
    aws_kms_key_id: str | None = Field(
        default=None,
        description="AWS KMS key ID",
    )
    aws_region: str | None = Field(
        default=None,
        description="AWS region for KMS",
    )

    # Local development key (optional — required if key_backend=local)
    local_vault_key: str | None = Field(
        default=None,
        description="64 hex chars — local dev encryption key (never use in production)",
    )

    # -----------------------------------------------------------------------
    # Application
    # -----------------------------------------------------------------------
    app_env: str = Field(
        default="development",
        description='"production" or "development"',
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    api_host: str = Field(
        default="0.0.0.0",
        description="API server bind address",
    )
    api_port: int = Field(
        default=8000,
        description="API server port",
    )

    # -----------------------------------------------------------------------
    # Token Vault
    # -----------------------------------------------------------------------
    vault_token_ttl_hours: int = Field(
        default=24,
        description="Hours before vault tokens expire",
    )

    # -----------------------------------------------------------------------
    # spaCy
    # -----------------------------------------------------------------------
    spacy_model: str = Field(
        default="en_core_web_lg",
        description="spaCy NER model name (must be downloaded before start)",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def async_database_url(self) -> str:
        """Convert standard postgresql:// URL to async asyncpg:// URL."""
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        return self.database_url


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings singleton.
    Call this function to get the settings instance — never instantiate directly.
    """
    return Settings()
