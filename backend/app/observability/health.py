"""Observability Subsystem Health Probes & Pipeline Integrity Evaluator.

Evaluates self-observability health, collector queue saturation, exporter availability,
cardinality limits, and performs end-to-end trace correlation validation across all 12 pipeline stages.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from pydantic import BaseModel, Field

from app.observability.collector import get_collector
from app.observability.metrics import get_metrics
from app.observability.slo import (
    ObservabilityCompletenessRecord,
    ObservabilityPipelineStage,
    ProductionSLORegistry,
)
from app.observability.tracing import (
    ATTR_DIRECTIVE_ID,
    ATTR_STAGE,
    ATTR_TASK_ID,
    ATTR_TENANT_ID,
    EnterpriseOSSpan,
    get_tracer,
)

logger = logging.getLogger(__name__)


class ObservabilityHealthReport(BaseModel):
    """Consolidated health report evaluating system and self-observability components."""

    status: str  # "HEALTHY" | "DEGRADED" | "CRITICAL"
    collector_alive: bool
    queue_saturation_ratio: float
    total_dropped_telemetry: int
    exporter_failures: int
    cardinality_violations: int
    pipeline_completeness_ratio: float
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = Field(default_factory=dict)


class ObservabilityPipelineIntegrityEvaluator:
    """Evaluates the mandatory Observability-Pipeline Integrity SLO (>= 99.99% completeness)."""

    REQUIRED_STAGES: list[ObservabilityPipelineStage] = [
        ObservabilityPipelineStage.FRONTEND_REQ,
        ObservabilityPipelineStage.API_TRACE,
        ObservabilityPipelineStage.IE_DAG,
        ObservabilityPipelineStage.WORKER,
        ObservabilityPipelineStage.SANDBOX_MANDATE,
        ObservabilityPipelineStage.PROVISIONER_RUNTIME,
        ObservabilityPipelineStage.HITL,
        ObservabilityPipelineStage.OUTBOUND_DISPATCH,
        ObservabilityPipelineStage.TELEMETRY,
        ObservabilityPipelineStage.W_LEARN,
        ObservabilityPipelineStage.PROV,
        ObservabilityPipelineStage.TERMINAL_CTS,
    ]

    def evaluate_directive_traces(
        self,
        directive_id: str,
        tenant_id: str,
        spans: list[EnterpriseOSSpan] | list[dict[str, Any]],
    ) -> ObservabilityCompletenessRecord:
        """Evaluate unbroken correlation, orphan spans, and stage completeness for a directive."""
        normalized_spans: list[dict[str, Any]] = [
            s.to_dict() if isinstance(s, EnterpriseOSSpan) else dict(s) for s in spans
        ]

        if not normalized_spans:
            return ObservabilityCompletenessRecord(
                directive_id=directive_id,
                tenant_id=tenant_id,
                root_trace_id="missing",
                missing_stages=list(self.REQUIRED_STAGES),
                complete=False,
                completeness_ratio=0.0,
            )

        root_trace_id = normalized_spans[0].get("trace_id", "unknown")
        all_span_ids = {s.get("span_id") for s in normalized_spans if s.get("span_id")}

        seen_stage_values = set()
        # Root ingress parent ID originates from the incoming client/caller context
        root_parent_ids = {normalized_spans[0].get("parent_span_id")} if normalized_spans else set()
        orphan_spans = 0
        missing_correlation_ids = []

        for s in normalized_spans:
            stg = s.get("stage") or s.get("attributes", {}).get(ATTR_STAGE)
            if stg:
                seen_stage_values.add(stg)

            # Check orphan spans: parent_span_id set but not in span_ids and not root ingress parent
            parent_id = s.get("parent_span_id") or s.get("attributes", {}).get("parent_span_id")
            if parent_id and parent_id not in all_span_ids and parent_id not in root_parent_ids:
                orphan_spans += 1

            # Check correlation IDs
            attrs = s.get("attributes", {})
            if ATTR_DIRECTIVE_ID not in attrs and "directive_id" not in attrs:
                missing_correlation_ids.append(f"span-{s.get('span_id')}-missing-directive_id")

        seen_stages: list[ObservabilityPipelineStage] = []
        missing_stages: list[ObservabilityPipelineStage] = []

        for req in self.REQUIRED_STAGES:
            if req.value in seen_stage_values:
                seen_stages.append(req)
            else:
                missing_stages.append(req)

        completeness_ratio = len(seen_stages) / len(self.REQUIRED_STAGES)
        is_complete = (len(missing_stages) == 0 and orphan_spans == 0)

        collector = get_collector()
        metrics = get_metrics()

        return ObservabilityCompletenessRecord(
            directive_id=directive_id,
            tenant_id=tenant_id,
            root_trace_id=root_trace_id,
            stages_seen=seen_stages,
            missing_stages=missing_stages,
            orphan_spans_count=orphan_spans,
            dropped_telemetry_count=collector.dropped_total,
            cardinality_violations_count=metrics.cardinality_protector.violations_count,
            missing_correlation_ids=missing_correlation_ids,
            complete=is_complete,
            completeness_ratio=round(completeness_ratio, 4),
        )


def check_observability_health() -> ObservabilityHealthReport:
    """Consolidated probe assessing health of the entire observability pipeline."""
    collector = get_collector()
    metrics = get_metrics()

    alive = collector.is_alive
    saturation = collector.queue_saturation_ratio
    dropped = collector.dropped_total
    exporter_fails = collector.exporter_failures
    cardinality_viols = metrics.cardinality_protector.violations_count

    # Determine overall status
    if not alive or exporter_fails > 10:
        status = "CRITICAL"
    elif saturation > 0.85 or dropped > 0 or cardinality_viols > 0:
        status = "DEGRADED"
    else:
        status = "HEALTHY"

    return ObservabilityHealthReport(
        status=status,
        collector_alive=alive,
        queue_saturation_ratio=round(saturation, 3),
        total_dropped_telemetry=dropped,
        exporter_failures=exporter_fails,
        cardinality_violations=cardinality_viols,
        pipeline_completeness_ratio=1.0 if dropped == 0 and alive else max(0.0, 1.0 - (dropped / 100.0)),
        details={
            "queue_size": collector.queue_size,
            "queue_capacity": collector.queue_capacity,
        },
    )
