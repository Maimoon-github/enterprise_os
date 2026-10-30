import uuid
from datetime import datetime

from app.schemas.common import BaseSchema, PlatformType


class CrossPlatformKPIs(BaseSchema):
    impressions_total: int
    clicks_total: int
    ctr_average: float
    conversions_total: int
    platforms_active: int


class AnomalyAlert(BaseSchema):
    platform: PlatformType
    metric: str
    z_score: float
    observed_value: float
    baseline_mean: float
    recommendation: str


class AnalyticsEventCreate(BaseSchema):
    brand_id: uuid.UUID
    platform: PlatformType
    external_post_id: str
    metric_type: str
    metric_value: float
    recorded_at: datetime | None = None


class AnalyticsEventResponse(BaseSchema):
    id: uuid.UUID
    brand_id: uuid.UUID
    platform: PlatformType
    external_post_id: str
    metric_type: str
    metric_value: float
    recorded_at: datetime
