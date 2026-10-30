import uuid
from datetime import datetime

from app.schemas.common import BaseSchema, PlatformType, TimestampedSchema


class ScheduleCreate(BaseSchema):
    campaign_id: uuid.UUID
    platform: PlatformType
    cron_expression: str | None = None
    scheduled_utc: datetime | None = None


class ScheduleResponse(TimestampedSchema):
    campaign_id: uuid.UUID
    platform: PlatformType
    cron_expression: str | None = None
    scheduled_utc: datetime | None = None
    status: str = "scheduled"
    idempotency_key: str
