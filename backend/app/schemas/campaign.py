import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import BaseSchema, PlatformType, TimestampedSchema
from pydantic import Field


class CampaignBase(BaseSchema):
    brand_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    objective: str = Field(..., min_length=1)


class CampaignCreate(CampaignBase):
    target_platforms: list[PlatformType] = Field(default_factory=list)


class CampaignUpdate(BaseSchema):
    name: str | None = Field(None, max_length=255)
    objective: str | None = None
    status: str | None = None
    blueprint: dict[str, Any] | None = None


class CampaignResponse(CampaignBase, TimestampedSchema):
    status: str
    blueprint: dict[str, Any] | None = None
    created_by: uuid.UUID | None = None
    updated_at: datetime
