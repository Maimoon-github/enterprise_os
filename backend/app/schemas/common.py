import uuid
from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

PlatformType = Literal[
    "linkedin",
    "youtube",
    "instagram",
    "threads",
    "facebook",
    "x",
    "pinterest",
    "google_business_profile",
]

SUPPORTED_PLATFORMS: list[str] = [
    "linkedin",
    "youtube",
    "instagram",
    "threads",
    "facebook",
    "x",
    "pinterest",
    "google_business_profile",
]


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TimestampedSchema(BaseSchema):
    id: uuid.UUID
    created_at: datetime


T = TypeVar("T")


class PaginatedResponse(BaseSchema, Generic[T]):
    items: list[T]
    total: int
    limit: int = 50
    offset: int = 0


# System Settings Schemas (for settings router)
class SettingsResponse(BaseSchema):
    encryption: str = "AES-256-GCM"
    sandbox_engine: str = "rootless-podman"
    primary_observability: str = "Langfuse (OTLP)"
    checkpointer: str = "PostgresSaver (Async)"
    target_platforms_count: int = 8
    allowed_platforms: list[PlatformType] = Field(default_factory=lambda: list(SUPPORTED_PLATFORMS))
    sandbox_limits: dict[str, Any] = Field(default_factory=dict)
    celery_queues: list[str] = Field(default_factory=list)
    beat_schedules_count: int = 3


class SettingsUpdateRequest(BaseSchema):
    settings: dict[str, Any]


# Observability Schemas (for observability router)
class ObservabilityTraceResponse(BaseSchema):
    exporter: str
    langfuse_host: str
    openinference_conventions: str
    total_spans_today: int


class ObservabilityStatsResponse(BaseSchema):
    trajectory_gate_pass_rate: float
    brand_voice_rubric_avg: float
    token_velocity_per_min: int
