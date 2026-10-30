from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from app.schemas.common import TimestampedSchema

class CampaignBase(BaseModel):
    brand_id: uuid.UUID
    name: str = Field(..., max_length=255)
    objective: str

class CampaignCreate(CampaignBase):
    target_platforms: list[str] = Field(default_factory=list)

class CampaignResponse(CampaignBase, TimestampedSchema):
    status: str
    blueprint: dict | None = None
    created_by: uuid.UUID | None = None
    updated_at: datetime
