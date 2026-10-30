from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from app.schemas.common import TimestampedSchema

class RunCreate(BaseModel):
    campaign_id: uuid.UUID
    user_command: str | None = None
    skills_override: list[str] | None = None

class RunResponse(TimestampedSchema):
    thread_id: str
    campaign_id: uuid.UUID
    status: str
    trigger_type: str
    current_node: str | None = None
    error_message: str | None = None
    token_usage: dict = Field(default_factory=dict)
    finished_at: datetime | None = None
