from pydantic import BaseModel


class CrossPlatformKPIs(BaseModel):
    impressions_total: int
    clicks_total: int
    ctr_average: float
    conversions_total: int
    platforms_active: int

class AnomalyAlert(BaseModel):
    platform: str
    metric: str
    z_score: float
    observed_value: float
    baseline_mean: float
    recommendation: str
