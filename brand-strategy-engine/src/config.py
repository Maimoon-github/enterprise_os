"""Runtime configuration loader for Universal AI Brand Strategy Engine."""

import os
from pathlib import Path
import tomllib
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class EngineConfig(BaseModel):
    version: str = "2.4.0"
    environment: str = "production-local"
    default_mode: str = "Mode_A_Personal"
    max_validator_revision_cycles: int = 3
    zero_hallucination_enforcement: bool = True
    evidence_storage_path: str = "/app/evidence_blobs"


class OllamaRuntimeConfig(BaseModel):
    base_url: str = Field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"))
    request_timeout_seconds: float = 180.0
    embedding_model: str = "nomic-embed-text:latest"


class ModelSpec(BaseModel):
    name: str
    temperature: float = 0.1
    context_window: int = 32768


class ModelsConfig(BaseModel):
    orchestrator: ModelSpec = Field(
        default_factory=lambda: ModelSpec(name="qwen2.5:14b-instruct-q4_K_M", temperature=0.1, context_window=32768)
    )
    analyst: ModelSpec = Field(
        default_factory=lambda: ModelSpec(name="llama3.2-vision:11b-instruct-q4_K_M", temperature=0.0, context_window=16384)
    )
    specialist: ModelSpec = Field(
        default_factory=lambda: ModelSpec(name="qwen2.5:14b-instruct-q4_K_M", temperature=0.2, context_window=16384)
    )
    growth: ModelSpec = Field(
        default_factory=lambda: ModelSpec(name="qwen2.5:14b-instruct-q4_K_M", temperature=0.2, context_window=32768)
    )
    validator: ModelSpec = Field(
        default_factory=lambda: ModelSpec(name="deepseek-r1:32b-qwen-distill-q4_K_M", temperature=0.0, context_window=32768)
    )


class VNCSandboxConfig(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv("VNC_HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(os.getenv("VNC_PORT", "5901")))
    display: str = Field(default_factory=lambda: os.getenv("DISPLAY", ":1"))
    viewport_width: int = 1920
    viewport_height: int = 1080
    color_depth: int = 24
    headless: bool = True
    screenshot_timeout_ms: int = 5000


class PostgresStorageConfig(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv("POSTGRES_HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    database: str = Field(default_factory=lambda: os.getenv("POSTGRES_DB", "brand_strategy_db"))
    user: str = Field(default_factory=lambda: os.getenv("POSTGRES_USER", "engine_user"))
    password: str = Field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "engine_secure_pass"))
    pool_size: int = 10
    vector_dimensions: int = 768

    @property
    def dsn(self) -> str:
        env_dsn = os.getenv("DATABASE_URL")
        if env_dsn:
            return env_dsn
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class AppConfig(BaseSettings):
    engine: EngineConfig = Field(default_factory=EngineConfig)
    ollama: OllamaRuntimeConfig = Field(default_factory=OllamaRuntimeConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    sandbox: VNCSandboxConfig = Field(default_factory=VNCSandboxConfig)
    storage: PostgresStorageConfig = Field(default_factory=PostgresStorageConfig)


def find_config_file() -> Optional[Path]:
    """Resolves config.toml from CONFIG_PATH environment variable or standard locations."""
    if "CONFIG_PATH" in os.environ:
        p = Path(os.environ["CONFIG_PATH"])
        if p.exists():
            return p

    # Standard locations relative to this file
    base_dir = Path(__file__).resolve().parent.parent
    candidate_paths = [
        base_dir / ".config" / "config.toml",
        base_dir.parent / "brand-strategy-engine" / ".config" / "config.toml",
        Path.cwd() / ".config" / "config.toml",
        Path("/app/.config/config.toml"),
    ]
    for candidate in candidate_paths:
        if candidate.exists():
            return candidate
    return None


def load_config() -> AppConfig:
    """Loads and merges configuration from .config/config.toml and environment variables."""
    cfg_file = find_config_file()
    raw_data: Dict[str, Any] = {}
    if cfg_file:
        try:
            with open(cfg_file, "rb") as f:
                raw_data = tomllib.load(f)
        except Exception:
            raw_data = {}

    engine_data = raw_data.get("engine", {})
    ollama_data = raw_data.get("runtime", {}).get("ollama", {})
    models_data = raw_data.get("models", {})
    sandbox_data = raw_data.get("sandbox", {}).get("vnc", {})
    postgres_data = raw_data.get("storage", {}).get("postgres", {})

    # Passwords and secrets from env take precedence
    if os.getenv("POSTGRES_PASSWORD"):
        postgres_data["password"] = os.getenv("POSTGRES_PASSWORD")
    elif not postgres_data.get("password"):
        postgres_data["password"] = os.getenv("POSTGRES_PASSWORD", "engine_secure_pass")

    if os.getenv("OLLAMA_BASE_URL"):
        ollama_data["base_url"] = os.getenv("OLLAMA_BASE_URL")

    if os.getenv("VNC_HOST"):
        sandbox_data["host"] = os.getenv("VNC_HOST")
    if os.getenv("VNC_PORT"):
        sandbox_data["port"] = int(os.getenv("VNC_PORT"))

    engine = EngineConfig(**engine_data) if engine_data else EngineConfig()
    ollama = OllamaRuntimeConfig(**ollama_data) if ollama_data else OllamaRuntimeConfig()

    models = ModelsConfig(
        orchestrator=ModelSpec(**models_data.get("orchestrator", {})) if "orchestrator" in models_data else ModelSpec(name="qwen2.5:14b-instruct-q4_K_M", temperature=0.1, context_window=32768),
        analyst=ModelSpec(**models_data.get("analyst", {})) if "analyst" in models_data else ModelSpec(name="llama3.2-vision:11b-instruct-q4_K_M", temperature=0.0, context_window=16384),
        specialist=ModelSpec(**models_data.get("specialist", {})) if "specialist" in models_data else ModelSpec(name="qwen2.5:14b-instruct-q4_K_M", temperature=0.2, context_window=16384),
        growth=ModelSpec(**models_data.get("growth", {})) if "growth" in models_data else ModelSpec(name="qwen2.5:14b-instruct-q4_K_M", temperature=0.2, context_window=32768),
        validator=ModelSpec(**models_data.get("validator", {})) if "validator" in models_data else ModelSpec(name="deepseek-r1:32b-qwen-distill-q4_K_M", temperature=0.0, context_window=32768),
    )

    sandbox = VNCSandboxConfig(**sandbox_data) if sandbox_data else VNCSandboxConfig()
    storage = PostgresStorageConfig(**postgres_data) if postgres_data else PostgresStorageConfig()

    return AppConfig(
        engine=engine,
        ollama=ollama,
        models=models,
        sandbox=sandbox,
        storage=storage,
    )


# Global singleton instance
CONFIG = load_config()
