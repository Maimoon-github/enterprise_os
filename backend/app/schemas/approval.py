import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import BaseSchema, TimestampedSchema


class ApprovalResumeRequest(BaseSchema):
    approved: bool
    notes: str | None = None
    modifications: dict[str, Any] | None = None


class ApprovalResponse(TimestampedSchema):
    run_id: uuid.UUID
    thread_id: str
    status: str
    step_name: str
    payload: dict[str, Any]
    decision_notes: str | None = None
    reviewed_by: uuid.UUID | None = None
    resolved_at: datetime | None = None
