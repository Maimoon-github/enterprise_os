"""OpenTelemetry Metrics Subsystem with Strict Cardinality Protection.

Enforces low-cardinality metric labels to prevent metric cardinality explosion,
tracks core Enterprise OS performance and reliability metrics, and provides self-observability
meters measuring telemetry drops, queue saturation, and exporter failures.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram, Meter, ObservableGauge
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

logger = logging.getLogger(__name__)

# Strict allowed low-cardinality label dimensions
ALLOWED_METRIC_DIMENSIONS = {
    "tenant_tier",
    "worker_role",
    "channel",
    "status",
    "stage",
    "error_type",
    "risk_level",
    "operation",
    "sli_id",
    "collector_id",
}

# Explicitly forbidden high-cardinality dimensions that must never be metric labels
FORBIDDEN_METRIC_DIMENSIONS = {
    "directive_id",
    "task_id",
    "attempt_id",
    "execution_id",
    "trace_id",
    "span_id",
    "traceparent",
    "idempotency_key",
    "record_id",
    "user_id",
}


class CardinalityProtector:
    """Enforces cardinality limits on metric attributes and tracks violations."""

    def __init__(self, max_cardinality_per_metric: int = 500) -> None:
        self._max_cardinality = max_cardinality_per_metric
        self._dimension_values: dict[str, set[str]] = defaultdict(set)
        self._violations_count = 0
        self._lock = threading.Lock()

    @property
    def violations_count(self) -> int:
        with self._lock:
            return self._violations_count

    def sanitize_attributes(self, metric_name: str, attributes: dict[str, Any] | None) -> dict[str, str]:
        """Strip forbidden high-cardinality attributes and cap unique dimension combinations."""
        if not attributes:
            return {}

        sanitized: dict[str, str] = {}
        with self._lock:
            for k, v in attributes.items():
                k_clean = k.lower().strip()
                if k_clean in FORBIDDEN_METRIC_DIMENSIONS:
                    self._violations_count += 1
                    logger.warning(
                        "Cardinality violation detected for metric %s: High-cardinality label '%s' stripped.",
                        metric_name,
                        k,
                    )
                    continue

                if k_clean not in ALLOWED_METRIC_DIMENSIONS:
                    self._violations_count += 1
                    logger.debug(
                        "Undeclared metric dimension '%s' on %s stripped by cardinality protector.",
                        k,
                        metric_name,
                    )
                    continue

                val_str = str(v)[:64]  # Bound string length
                val_set = self._dimension_values[k_clean]
                if len(val_set) >= self._max_cardinality and val_str not in val_set:
                    self._violations_count += 1
                    val_str = "_overflow_"

                val_set.add(val_str)
                sanitized[k_clean] = val_str

        return sanitized


class EnterpriseOSMetrics:
    """Central metrics facade managing OpenTelemetry instruments and cardinality defense."""

    def __init__(self, service_name: str = "enterprise_os") -> None:
        self.service_name = service_name
        self.cardinality_protector = CardinalityProtector()
        self._metric_reader = InMemoryMetricReader()
        self._meter_provider = MeterProvider(metric_readers=[self._metric_reader])
        self._meter: Meter = self._meter_provider.get_meter(service_name, "1.0.0")

        # In-memory accumulator for rapid SLI evaluations
        self._raw_observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._lock = threading.Lock()

        # Self-observability gauge states
        self._collector_queue_saturation: float = 0.0

        self._init_instruments()

    def _init_instruments(self) -> None:
        # 1. Directives
        self.directive_total: Counter = self._meter.create_counter(
            name="enterprise_os.directive.total",
            description="Total count of directives submitted for orchestration",
            unit="1",
        )
        self.directive_duration: Histogram = self._meter.create_histogram(
            name="enterprise_os.directive.duration",
            description="Total wall-clock duration of completed directives",
            unit="s",
        )

        # 2. Sandboxes & Specialists
        self.sandbox_provision_total: Counter = self._meter.create_counter(
            name="enterprise_os.sandbox.provision.total",
            description="Total physical sandbox provisioning requests",
            unit="1",
        )
        self.sandbox_provision_duration: Histogram = self._meter.create_histogram(
            name="enterprise_os.sandbox.provision.duration",
            description="Latency for physical sandbox cgroup/namespace allocation",
            unit="s",
        )
        self.sandbox_execution_duration: Histogram = self._meter.create_histogram(
            name="enterprise_os.sandbox.execution.duration",
            description="Latency for specialist execution inside physical sandbox",
            unit="s",
        )

        # 3. HITL Gate
        self.hitl_decisions_total: Counter = self._meter.create_counter(
            name="enterprise_os.hitl.decisions.total",
            description="Total HITL reviews completed",
            unit="1",
        )
        self.hitl_waiting_duration: Histogram = self._meter.create_histogram(
            name="enterprise_os.hitl.waiting.duration",
            description="Human reviewer wait time before decision",
            unit="s",
        )
        self.hitl_processing_duration: Histogram = self._meter.create_histogram(
            name="enterprise_os.hitl.processing.duration",
            description="Cryptographic and validation processing latency for HITL decision",
            unit="s",
        )

        # 4. Outbound Actuation
        self.outbound_actuation_total: Counter = self._meter.create_counter(
            name="enterprise_os.outbound.actuation.total",
            description="Total outbound platform actuation dispatches",
            unit="1",
        )
        self.outbound_duplicate_prevented: Counter = self._meter.create_counter(
            name="enterprise_os.outbound.duplicate_prevented.total",
            description="Total real-world duplicate mutations prevented via idempotency/reconciliation",
            unit="1",
        )
        self.outbound_actuation_duration: Histogram = self._meter.create_histogram(
            name="enterprise_os.outbound.actuation.duration",
            description="Outbound actuation latency to external platform acknowledgement",
            unit="s",
        )

        # 5. Telemetry Intake
        self.telemetry_admitted_total: Counter = self._meter.create_counter(
            name="enterprise_os.telemetry.admitted.total",
            description="Total incoming telemetry records admitted into intake queue",
            unit="1",
        )
        self.telemetry_ingestion_lag: Histogram = self._meter.create_histogram(
            name="enterprise_os.telemetry.ingestion_lag",
            description="Lag between telemetry receipt admission and work item completion",
            unit="s",
        )

        # 6. Observability Pipeline Self-Monitoring Instruments
        self.observability_spans_emitted: Counter = self._meter.create_counter(
            name="enterprise_os.observability.spans.emitted",
            description="Total distributed tracing spans emitted",
            unit="1",
        )
        self.observability_spans_dropped: Counter = self._meter.create_counter(
            name="enterprise_os.observability.spans.dropped",
            description="Total distributed tracing spans dropped due to queue saturation or failures",
            unit="1",
        )
        self.observability_cardinality_violations: Counter = self._meter.create_counter(
            name="enterprise_os.observability.cardinality_violations",
            description="Total violations where high-cardinality labels were stripped",
            unit="1",
        )
        self.observability_exporter_failures: Counter = self._meter.create_counter(
            name="enterprise_os.observability.exporter_failures",
            description="Total failures encountered when exporting to monitoring collector",
            unit="1",
        )

    # -------------------------------------------------------------------------
    # Recording Helpers with Cardinality Defense
    # -------------------------------------------------------------------------
    def record_directive(self, status: str, duration_seconds: float, attributes: dict[str, Any] | None = None) -> None:
        attrs = dict(attributes or {})
        attrs["status"] = status
        sanitized = self.cardinality_protector.sanitize_attributes("directive", attrs)

        self.directive_total.add(1, sanitized)
        self.directive_duration.record(duration_seconds, sanitized)

        with self._lock:
            self._raw_observations["directive"].append({
                "status": status,
                "duration_seconds": duration_seconds,
                "timestamp": time.time(),
                "attributes": sanitized,
            })

    def record_sandbox_provisioning(self, duration_seconds: float, worker_role: str, status: str = "success") -> None:
        attrs = {"worker_role": worker_role, "status": status}
        sanitized = self.cardinality_protector.sanitize_attributes("sandbox_provision", attrs)

        self.sandbox_provision_total.add(1, sanitized)
        self.sandbox_provision_duration.record(duration_seconds, sanitized)

        with self._lock:
            self._raw_observations["sandbox_provision"].append({
                "duration_seconds": duration_seconds,
                "status": status,
                "timestamp": time.time(),
            })

    def record_sandbox_execution(self, duration_seconds: float, worker_role: str, status: str = "success") -> None:
        attrs = {"worker_role": worker_role, "status": status}
        sanitized = self.cardinality_protector.sanitize_attributes("sandbox_execution", attrs)

        self.sandbox_execution_duration.record(duration_seconds, sanitized)
        with self._lock:
            self._raw_observations["sandbox_execution"].append({
                "duration_seconds": duration_seconds,
                "status": status,
                "timestamp": time.time(),
            })

    def record_hitl(self, waiting_seconds: float, processing_seconds: float, status: str = "approved") -> None:
        attrs = {"status": status}
        sanitized = self.cardinality_protector.sanitize_attributes("hitl", attrs)

        self.hitl_decisions_total.add(1, sanitized)
        self.hitl_waiting_duration.record(waiting_seconds, sanitized)
        self.hitl_processing_duration.record(processing_seconds, sanitized)

        with self._lock:
            self._raw_observations["hitl"].append({
                "waiting_seconds": waiting_seconds,
                "processing_seconds": processing_seconds,
                "status": status,
                "timestamp": time.time(),
            })

    def record_outbound(
        self,
        duration_seconds: float,
        channel: str,
        status: str = "success",
        duplicate_prevented: bool = False,
    ) -> None:
        attrs = {"channel": channel, "status": status}
        sanitized = self.cardinality_protector.sanitize_attributes("outbound", attrs)

        self.outbound_actuation_total.add(1, sanitized)
        self.outbound_actuation_duration.record(duration_seconds, sanitized)
        if duplicate_prevented:
            self.outbound_duplicate_prevented.add(1, sanitized)

        with self._lock:
            self._raw_observations["outbound"].append({
                "duration_seconds": duration_seconds,
                "status": status,
                "duplicate_prevented": duplicate_prevented,
                "timestamp": time.time(),
            })

    def record_telemetry_lag(self, lag_seconds: float, status: str = "admitted") -> None:
        attrs = {"status": status}
        sanitized = self.cardinality_protector.sanitize_attributes("telemetry", attrs)

        self.telemetry_admitted_total.add(1, sanitized)
        self.telemetry_ingestion_lag.record(lag_seconds, sanitized)

        with self._lock:
            self._raw_observations["telemetry"].append({
                "lag_seconds": lag_seconds,
                "status": status,
                "timestamp": time.time(),
            })

    def record_self_observability(
        self,
        spans_emitted: int = 0,
        spans_dropped: int = 0,
        exporter_failures: int = 0,
        queue_saturation: float = 0.0,
    ) -> None:
        self._collector_queue_saturation = max(0.0, min(1.0, queue_saturation))
        if spans_emitted > 0:
            self.observability_spans_emitted.add(spans_emitted)
        if spans_dropped > 0:
            self.observability_spans_dropped.add(spans_dropped)
        if exporter_failures > 0:
            self.observability_exporter_failures.add(exporter_failures)

        # Sync violation count with counter
        v = self.cardinality_protector.violations_count
        if v > 0:
            self.observability_cardinality_violations.add(1)

    def get_raw_observations(self, metric_key: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._raw_observations.get(metric_key, []))

    def reset(self) -> None:
        with self._lock:
            self._raw_observations.clear()
            self._collector_queue_saturation = 0.0


# Global singleton instance
_metrics_instance: EnterpriseOSMetrics | None = None
_metrics_lock = threading.Lock()


def get_metrics() -> EnterpriseOSMetrics:
    global _metrics_instance
    with _metrics_lock:
        if _metrics_instance is None:
            _metrics_instance = EnterpriseOSMetrics()
        return _metrics_instance
