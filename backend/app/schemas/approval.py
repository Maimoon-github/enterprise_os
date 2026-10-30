import uuid
from datetime import datetime

from app.schemas.common import TimestampedSchema
from pydantic import BaseModel


class ApprovalResumeRequest(BaseModel):
    approved: bool
    notes: str | None = None
    modifications: dict | None = None

class ApprovalResponse(TimestampedSchema):
    run_id: uuid.UUID
    thread_id: str
    status: str
    step_name: str
    payload: dict
    decision_notes: str | None = None
    reviewed_by: uuid.UUID | None = None
    resolved_at: datetime | None = None
