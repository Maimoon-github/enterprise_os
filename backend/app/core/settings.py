"""Runtime settings and external credential/reference configuration."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BACKEND_", env_file=".env", extra="ignore")

    app_name: str = "governed-backend"
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "postgresql+psycopg://localhost:5432/backend"
    llm_provider: str = "openai-compatible"
    sandbox_sdk_path: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
