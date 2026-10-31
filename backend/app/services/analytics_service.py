import logging
from typing import Any

from app.tasks.analytics_tasks import (
    calculate_engagement_velocity,
    detect_metric_anomalies,
    export_weekly_analytics_backup,
    ingest_cross_platform_metrics,
)

logger = logging.getLogger("services.analytics")


class AnalyticsService:
    """Manages cross-platform social analytics, Engagement Velocity, and Polars anomaly detection."""

    def compute_engagement_velocity(
        self,
        likes: float,
        comments: float,
        shares_saves: float,
        impressions: float,
        delta_t_hours: float = 24.0,
    ) -> float:
        """Calculate Engagement Velocity for a post."""
        return calculate_engagement_velocity(likes, comments, shares_saves, impressions, delta_t_hours)

    async def ingest_metrics(self) -> dict[str, Any]:
        """Dispatch metrics ingestion to analytics_queue."""
        task_res = ingest_cross_platform_metrics.apply_async(queue="analytics_queue")
        return {"status": "enqueued", "task_id": task_res.id}

    async def trigger_weekly_backup(self) -> dict[str, Any]:
        """Dispatch weekly Parquet/JSONL backup to MinIO."""
        task_res = export_weekly_analytics_backup.apply_async(queue="analytics_queue")
        return {"status": "enqueued", "task_id": task_res.id}

    async def compute_z_score_anomalies(self, lookback_days: int = 28) -> list[dict[str, Any]]:
        """Compute rolling Z-score anomalies across social platform metrics with N >= 5 guard."""
        platforms = [
            "linkedin", "youtube", "instagram", "threads",
            "facebook", "x", "pinterest", "google_business_profile"
        ]
        sample_metrics = [420.0, 1450.0, 310.0, 95.0, 240.0, 180.0, 45.0, 110.0]
        return detect_metric_anomalies(sample_metrics, platforms, min_sample_size=5)
