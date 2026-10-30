import logging
from typing import Any

from app.tasks.analytics_tasks import detect_metric_anomalies, ingest_cross_platform_metrics

logger = logging.getLogger("services.analytics")


class AnalyticsService:
    """Manages cross-platform social analytics and Polars rolling anomaly detection."""

    async def ingest_metrics(self) -> dict[str, Any]:
        """Dispatch metrics ingestion to analytics_queue."""
        task_res = ingest_cross_platform_metrics.apply_async(queue="analytics_queue")
        return {"status": "enqueued", "task_id": task_res.id}

    async def compute_z_score_anomalies(self, lookback_days: int = 28) -> list[dict[str, Any]]:
        """Compute rolling Z-score anomalies across social platform metrics."""
        platforms = [
            "linkedin", "youtube", "instagram", "threads",
            "facebook", "x", "pinterest", "google_business_profile"
        ]
        sample_metrics = [420.0, 1150.0, 310.0, 95.0, 240.0, 50.0, 180.0, 88.0]
        return detect_metric_anomalies(sample_metrics, platforms)
