import json
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "Agentic Brand Marketing OS"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change_this_to_a_secure_random_64_char_hex_string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOWED_ORIGINS: Any = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:

        if isinstance(v, str):
            if v.strip().startswith("["):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        if isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]


    # Database
    DATABASE_URL: str = "postgresql+asyncpg://marketing_os:marketing_os_secret@localhost:5432/marketing_os_db"
    SYNC_DATABASE_URL: str = "postgresql://marketing_os:marketing_os_secret@localhost:5432/marketing_os_db"

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL_SUPERVISOR: str = "llama3.3:70b"
    OLLAMA_MODEL_WORKER: str = "qwen2.5:14b"
    OLLAMA_MODEL_EMBEDDING: str = "nomic-embed-text"

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ROOT_USER: str = "minio_admin"
    MINIO_ROOT_PASSWORD: str = "minio_admin_secret"
    MINIO_BUCKET_RAW: str = "marketing-raw-assets"
    MINIO_BUCKET_GENERATED: str = "marketing-generated-assets"
    MINIO_USE_SSL: bool = False

    # Observability
    OTEL_SERVICE_NAME: str = "agentic-marketing-os"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318/v1/traces"
    LANGFUSE_PUBLIC_KEY: str = "pk-lf-local-key"
    LANGFUSE_SECRET_KEY: str = "sk-lf-local-secret"
    LANGFUSE_HOST: str = "http://localhost:3001"
    PHOENIX_ENABLED: bool = False

    # Podman Sandbox
    PODMAN_SOCKET_PATH: str = "/run/user/1000/podman/podman.sock"
    SANDBOX_IMAGE: str = "marketing-os-worker-sandbox:latest"

settings = Settings()
