"""Runtime settings and external credential/reference configuration.

All environment-specific values and secrets are sourced exclusively from the
process environment (or an ``.env`` file in local development). Nothing in
this module hard-codes a secret, hostname, or environment-specific value.
See ``.env.example`` at the repository root for the full list of supported
variables.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL/pgvector/TimescaleDB connection boundary configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_", extra="ignore")

    dsn: str = Field(
        default="postgresql+asyncpg://localhost:5432/governed_backend",
        description="SQLAlchemy async connection string for the system of record.",
    )
    migration_dsn: str | None = Field(
        default=None,
        description="Separate migration/admin connection string for DDL execution.",
    )
    pool_min_size: int = Field(default=1, ge=0)
    pool_max_size: int = Field(default=10, ge=1)
    statement_timeout_seconds: int = Field(default=30, ge=1)
    enforce_rls: bool = Field(
        default=True,
        description="Whether to enforce tenant RLS context on sessions.",
    )
    require_non_privileged_role: bool = Field(
        default=False,
        description="Fail closed if runtime role is superuser, table owner, or BYPASSRLS.",
    )


class LlmSettings(BaseSettings):
    """Provider-neutral AI model boundary configuration with local-model priority."""

    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")

    provider: str = Field(
        default="unset",
        description="Configured model provider identifier ('local', 'ollama', 'vllm', 'openai', etc.).",
    )
    api_key: str | None = Field(default=None, repr=False)
    base_url: str | None = Field(
        default=None,
        description="Base URL for OpenAI-compatible completions (e.g. http://localhost:11434/v1).",
    )
    model_name: str = Field(default="unset")
    request_timeout_seconds: int = Field(default=60, ge=1)
    cost_per_million_input_tokens: float = Field(default=0.0, ge=0.0)
    cost_per_million_output_tokens: float = Field(default=0.0, ge=0.0)
    max_budget_per_task: float = Field(default=100.0, ge=0.0)

    @property
    def is_local(self) -> bool:
        """Check whether the configured provider represents a local/self-hosted model."""
        if self.provider.lower() in {"local", "ollama", "vllm", "lmstudio", "localai"}:
            return True
        if self.base_url and ("localhost" in self.base_url or "127.0.0.1" in self.base_url):
            return True
        return False


class SandboxSettings(BaseSettings):
    """Configuration for Sandbox Control Plane and agent_sandbox boundary."""

    model_config = SettingsConfigDict(env_prefix="SANDBOX_", extra="ignore")

    environment: str | None = Field(default=None)
    endpoint: str | None = Field(default=None)
    api_key: str | None = Field(default=None, repr=False)
    proxy_endpoint: str | None = Field(default="http://aio-egress-proxy:8118")
    default_network_policy: str = Field(default="deny_all")
    default_timeout_seconds: int = Field(default=120, ge=1)
    workspace_base_dir: str = Field(default="ephemeral_workspaces")
    seccomp_profile_path: str = Field(default="worker-seccomp.json")
    isolate_network: bool = Field(default=True)
    enforce_microvm_isolation: bool = Field(default=True)
    pids_limit: int = Field(default=1024, ge=32, le=4096)
    max_memory_mb: int = Field(default=4096, ge=128, le=8192)
    max_cpu_cores: float = Field(default=2.0, ge=0.1, le=4.0)


class CmsSettings(BaseSettings):
    """Headless CMS integration boundary configuration."""

    model_config = SettingsConfigDict(env_prefix="CMS_", extra="ignore")

    base_url: str | None = Field(default=None)
    api_key: str | None = Field(default=None, repr=False)


class AdsSettings(BaseSettings):
    """Paid-media platform adapter configuration."""

    model_config = SettingsConfigDict(env_prefix="ADS_", extra="ignore")

    meta_access_token: str | None = Field(default=None, repr=False)
    google_access_token: str | None = Field(default=None, repr=False)
    tiktok_access_token: str | None = Field(default=None, repr=False)
    linkedin_access_token: str | None = Field(default=None, repr=False)


class SocialSettings(BaseSettings):
    """Organic social-channel adapter configuration."""

    model_config = SettingsConfigDict(env_prefix="SOCIAL_", extra="ignore")

    instagram_access_token: str | None = Field(default=None, repr=False)
    x_access_token: str | None = Field(default=None, repr=False)
    tiktok_access_token: str | None = Field(default=None, repr=False)
    youtube_access_token: str | None = Field(default=None, repr=False)


class SecuritySettings(BaseSettings):
    """Cryptographic and authorization configuration."""

    model_config = SettingsConfigDict(env_prefix="SECURITY_", extra="ignore")

    signing_public_key_pem: str | None = Field(default=None, repr=False)
    require_signed_dispatch: bool = Field(default=True)


class TelemetrySettings(BaseSettings):
    """Omnichannel Telemetry Engine and listener configuration."""

    model_config = SettingsConfigDict(env_prefix="TELEMETRY_", extra="ignore")

    webhook_signing_secret: str | None = Field(default=None, repr=False)
    max_payload_bytes: int = Field(default=262144, ge=1024)
    freshness_window_seconds: int = Field(default=3600, ge=1)
    max_future_skew_seconds: int = Field(default=60, ge=0)
    enable_synthetic_probes: bool = Field(default=True)


class Settings(BaseSettings):
    """Aggregate application settings composition root."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)
    cms: CmsSettings = Field(default_factory=CmsSettings)
    ads: AdsSettings = Field(default_factory=AdsSettings)
    social: SocialSettings = Field(default_factory=SocialSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached settings instance."""

    return Settings()