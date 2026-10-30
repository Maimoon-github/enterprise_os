import uuid
from datetime import datetime

from pydantic import BaseModel


class ScheduleResponse(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    platform: str
    cron_expression: str | None
    scheduled_utc: datetime | None
    status: str
    idempotency_key: str
