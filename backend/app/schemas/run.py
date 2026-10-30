import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import BaseSchema, TimestampedSchema
from pydantic import Field


class RunCreate(BaseSchema):
    campaign_id: uuid.UUID
    user_command: str | None = None
    skills_override: list[str] | None = None


class RunResponse(TimestampedSchema):
    thread_id: str
    campaign_id: uuid.UUID
    status: str
    trigger_type: str = "manual"
    current_node: str | None = None
    error_message: str | None = None
    token_usage: dict[str, Any] = Field(default_factory=dict)
    finished_at: datetime | None = None
