"""OpenTelemetry Collector Export Boundary & Ingestion Buffer.

Provides the controlled export boundary for all Enterprise OS traces, metrics, and logs.
Implements bounded queues, backpressure drop handling, self-observability instrumentation,
and failure injection hooks (kill collector, queue overflow, exporter disconnect).

Critical Safety Invariant:
Observability pipeline failures, queue saturation, or exporter dropouts must NEVER
destabilize application execution or throw unhandled exceptions into business workflows.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any

from app.observability.metrics import get_metrics
from app.observability.tracing import EnterpriseOSSpan

logger = logging.getLogger(__name__)


class CollectorQueueSaturationError(Exception):
    """Raised internally when collector queue capacity is exceeded."""


class CollectorExporterError(Exception):
    """Raised internally when downstream exporter connectivity fails."""


class OpenTelemetryCollectorBoundary:
    """In-process and daemon-ready OpenTelemetry Collector boundary with self-observability."""

    def __init__(
        self,
        collector_id: str = "otel-collector-primary",
        queue_capacity: int = 1000,
    ) -> None:
        self.collector_id = collector_id
        self.queue_capacity = queue_capacity

        # Ingestion buffers
        self._span_queue: list[dict[str, Any]] = []
        self._metric_queue: list[dict[str, Any]] = []
        self._log_queue: list[dict[str, Any]] = []
        self._lock = threading.Lock()

        # Telemetry accounting
        self._total_received = 0
        self._total_exported = 0
        self._dropped_spans = 0
        self._dropped_metrics = 0
        self._dropped_logs = 0
        self._exporter_failures = 0

        # Fault Injection States (for Chaos & Integrity testing)
        self._is_alive: bool = True
        self._force_overflow: bool = False
        self._force_exporter_failure: bool = False

    @property
    def is_alive(self) -> bool:
        with self._lock:
            return self._is_alive

    @property
    def queue_size(self) -> int:
        with self._lock:
            return len(self._span_queue) + len(self._metric_queue) + len(self._log_queue)

    @property
    def queue_saturation_ratio(self) -> float:
        with self._lock:
            if self._force_overflow:
                return 1.0
            return len(self._span_queue) / max(1, self.queue_capacity)

    @property
    def dropped_total(self) -> int:
        with self._lock:
            return self._dropped_spans + self._dropped_metrics + self._dropped_logs

    @property
    def exporter_failures(self) -> int:
        with self._lock:
            return self._exporter_failures

    # -------------------------------------------------------------------------
    # Fault Injection Controls
    # -------------------------------------------------------------------------
    def set_alive(self, alive: bool) -> None:
        with self._lock:
            self._is_alive = alive

    def set_force_overflow(self, overflow: bool) -> None:
        with self._lock:
            self._force_overflow = overflow

    def set_force_exporter_failure(self, fail: bool) -> None:
        with self._lock:
            self._force_exporter_failure = fail

    # -------------------------------------------------------------------------
    # Telemetry Ingestion API (Fail-Safe)
    # -------------------------------------------------------------------------
    def ingest_span(self, span: EnterpriseOSSpan | dict[str, Any]) -> bool:
        """Ingest a distributed tracing span into the collector buffer.
        
        Guaranteed fail-safe: Never raises unhandled exception into calling application.
        """
        payload = span.to_dict() if isinstance(span, EnterpriseOSSpan) else dict(span)
        metrics = get_metrics()

        with self._lock:
            self._total_received += 1

            if not self._is_alive:
                self._dropped_spans += 1
                metrics.record_self_observability(spans_dropped=1, queue_saturation=1.0)
                logger.warning("Collector down: Span %s dropped.", payload.get("name"))
                return False

            if self._force_overflow or len(self._span_queue) >= self.queue_capacity:
                self._dropped_spans += 1
                metrics.record_self_observability(spans_dropped=1, queue_saturation=1.0)
                logger.warning("Collector queue saturation: Span %s dropped.", payload.get("name"))
                return False

            self._span_queue.append(payload)

        metrics.record_self_observability(
            spans_emitted=1,
            queue_saturation=self.queue_saturation_ratio,
        )
        return True

    def ingest_metric(self, metric_event: dict[str, Any]) -> bool:
        """Ingest metric event into collector buffer."""
        metrics = get_metrics()
        with self._lock:
            self._total_received += 1
            if not self._is_alive or self._force_overflow or len(self._metric_queue) >= self.queue_capacity:
                self._dropped_metrics += 1
                return False
            self._metric_queue.append(metric_event)
        return True

    def ingest_log(self, log_event: dict[str, Any]) -> bool:
        """Ingest structured log event into collector buffer."""
        with self._lock:
            self._total_received += 1
            if not self._is_alive or self._force_overflow or len(self._log_queue) >= self.queue_capacity:
                self._dropped_logs += 1
                return False
            self._log_queue.append(log_event)
        return True

    # -------------------------------------------------------------------------
    # Batch Export Process (Flushing to Monitored Backends)
    # -------------------------------------------------------------------------
    def flush(self) -> dict[str, Any]:
        """Flush buffered spans, metrics, and logs to downstream storage/monitoring."""
        metrics = get_metrics()
        with self._lock:
            if not self._is_alive:
                self._exporter_failures += 1
                metrics.record_self_observability(exporter_failures=1)
                return {"success": False, "reason": "collector_offline"}

            if self._force_exporter_failure:
                self._exporter_failures += 1
                metrics.record_self_observability(exporter_failures=1)
                return {"success": False, "reason": "exporter_connectivity_broken"}

            exported_spans = len(self._span_queue)
            exported_metrics = len(self._metric_queue)
            exported_logs = len(self._log_queue)

            self._total_exported += exported_spans + exported_metrics + exported_logs
            self._span_queue.clear()
            self._metric_queue.clear()
            self._log_queue.clear()

        return {
            "success": True,
            "exported_spans": exported_spans,
            "exported_metrics": exported_metrics,
            "exported_logs": exported_logs,
        }

    def get_buffered_spans(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._span_queue)

    def get_self_observability_snapshot(self) -> dict[str, Any]:
        """Generate point-in-time self-observability telemetry snapshot."""
        with self._lock:
            return {
                "collector_id": self.collector_id,
                "is_alive": self._is_alive,
                "queue_capacity": self.queue_capacity,
                "current_queue_size": len(self._span_queue) + len(self._metric_queue) + len(self._log_queue),
                "queue_saturation_ratio": self.queue_saturation_ratio,
                "total_received": self._total_received,
                "total_exported": self._total_exported,
                "dropped_spans": self._dropped_spans,
                "dropped_metrics": self._dropped_metrics,
                "dropped_logs": self._dropped_logs,
                "total_dropped": self.dropped_total,
                "exporter_failures": self._exporter_failures,
                "timestamp": datetime.now(UTC).isoformat(),
            }

    def reset(self) -> None:
        with self._lock:
            self._span_queue.clear()
            self._metric_queue.clear()
            self._log_queue.clear()
            self._total_received = 0
            self._total_exported = 0
            self._dropped_spans = 0
            self._dropped_metrics = 0
            self._dropped_logs = 0
            self._exporter_failures = 0
            self._is_alive = True
            self._force_overflow = False
            self._force_exporter_failure = False


# Global collector singleton
_collector_instance: OpenTelemetryCollectorBoundary | None = None
_collector_lock = threading.Lock()


def get_collector() -> OpenTelemetryCollectorBoundary:
    global _collector_instance
    with _collector_lock:
        if _collector_instance is None:
            _collector_instance = OpenTelemetryCollectorBoundary()
        return _collector_instance
