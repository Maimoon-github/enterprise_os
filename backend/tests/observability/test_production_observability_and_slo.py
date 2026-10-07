"""Production Observability, OpenTelemetry Collector & SLO Certification Test Suite.

Proves:
1. Canonical SLO Registry coverage including Observability-Pipeline Integrity (>= 99.99%).
2. OpenTelemetry metrics with strict Cardinality Protection.
3. W3C Trace Context propagation across all 12 pipeline stages.
4. OpenTelemetry Collector boundary buffering, drops, and batch export.
5. Error budget calculation, exhaustion forecasting, and Google SRE multi-window burn alerts (1h / 6h).
6. Observability failure injection (Collector down, queue overflow, broken exporter) maintaining fail-safe application continuity.
7. End-to-end governed directive execution answering all 11 operator exit criteria directly from telemetry.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
import pytest

from app.core.trace_context import W3CTraceContext
from app.observability.collector import (
    OpenTelemetryCollectorBoundary,
    get_collector,
)
from app.observability.directive_runner import (
    InstrumentedDirectiveExecutionHarness,
)
from app.observability.error_budget import (
    AlertSeverity,
    ErrorBudgetCalculator,
)
from app.observability.health import (
    ObservabilityPipelineIntegrityEvaluator,
    check_observability_health,
)
from app.observability.metrics import (
    CardinalityProtector,
    EnterpriseOSMetrics,
    get_metrics,
)
from app.observability.slo import (
    ObservabilityPipelineStage,
    ProductionSLORegistry,
    SLIComparison,
    SLOCategory,
)
from app.observability.slo_evaluator import (
    ProductionSLOEvaluator,
)
from app.observability.tracing import (
    ATTR_DIRECTIVE_ID,
    ATTR_STAGE,
    ATTR_TASK_ID,
    ATTR_TENANT_ID,
    get_tracer,
)


@pytest.fixture(autouse=True)
def reset_observability_singletons() -> None:
    """Ensure clean metrics, tracer, and collector buffers between tests."""
    get_metrics().reset()
    get_tracer().clear()
    get_collector().reset()


# =============================================================================
# 1. SLO Registry & Canonical Definitions
# =============================================================================
def test_slo_registry_coverage() -> None:
    """Verify all certified production SLOs exist with expected targets and units."""
    registry = ProductionSLORegistry()
    all_slos = registry.list_all()

    assert len(all_slos) >= 12, f"Expected at least 12 production SLOs, found {len(all_slos)}"

    # Check Critical Invariant: Observability-Pipeline Completeness SLO
    pipeline_slo = registry.get("slo_observability_pipeline_completeness")
    assert pipeline_slo is not None, "Observability-Pipeline Completeness SLO must exist."
    assert pipeline_slo.category == SLOCategory.OBSERVABILITY_PIPELINE
    assert pipeline_slo.target_value == 99.99
    assert pipeline_slo.comparison == SLIComparison.GREATER_THAN_OR_EQUAL
    assert pipeline_slo.unit == "%"

    # Check Outbound Zero Duplicate Guarantee
    outbound_slo = registry.get("slo_outbound_actuation_zero_duplicate")
    assert outbound_slo is not None
    assert outbound_slo.target_value == 100.0

    # Check Database DR SLOs
    rpo_slo = registry.get("slo_database_pitr_rpo")
    assert rpo_slo is not None and rpo_slo.target_value == 1.0
    rto_slo = registry.get("slo_database_pitr_rto")
    assert rto_slo is not None and rto_slo.target_value == 15.0


# =============================================================================
# 2. Metrics & Strict Cardinality Protection
# =============================================================================
def test_metric_cardinality_protector_enforcement() -> None:
    """Verify high-cardinality labels are stripped and counted as violations."""
    protector = CardinalityProtector(max_cardinality_per_metric=10)

    # Valid low-cardinality attributes
    valid_attrs = {
        "tenant_tier": "enterprise",
        "worker_role": "W_DEV",
        "channel": "meta",
        "status": "COMPLETED",
    }
    sanitized = protector.sanitize_attributes("test_metric", valid_attrs)
    assert sanitized["tenant_tier"] == "enterprise"
    assert sanitized["worker_role"] == "W_DEV"
    assert sanitized["channel"] == "meta"
    assert sanitized["status"] == "COMPLETED"
    assert protector.violations_count == 0

    # High-cardinality attributes that must be stripped
    forbidden_attrs = {
        "directive_id": "dir-12345678",
        "task_id": "task-87654321",
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "idempotency_key": "idemp-unique-999",
        "worker_role": "W_STRAT",
    }
    sanitized_forbidden = protector.sanitize_attributes("test_metric", forbidden_attrs)
    assert "directive_id" not in sanitized_forbidden
    assert "task_id" not in sanitized_forbidden
    assert "trace_id" not in sanitized_forbidden
    assert "idempotency_key" not in sanitized_forbidden
    assert sanitized_forbidden["worker_role"] == "W_STRAT"
    assert protector.violations_count == 4


# =============================================================================
# 3. W3C Trace Context Propagation
# =============================================================================
def test_w3c_trace_context_propagation() -> None:
    """Verify parent-to-child span context propagation and header injection."""
    root_ctx = W3CTraceContext.new()
    assert len(root_ctx.trace_id) == 32
    assert len(root_ctx.span_id) == 16
    assert root_ctx.traceparent.startswith("00-")

    child_ctx = root_ctx.child_span()
    assert child_ctx.trace_id == root_ctx.trace_id
    assert child_ctx.parent_span_id == root_ctx.span_id
    assert child_ctx.span_id != root_ctx.span_id

    headers = child_ctx.inject_headers({"X-Custom": "test"})
    assert headers["traceparent"] == child_ctx.traceparent
    assert headers["X-Custom"] == "test"

    parsed = W3CTraceContext.parse(headers["traceparent"])
    assert parsed is not None
    assert parsed.trace_id == child_ctx.trace_id
    assert parsed.span_id == child_ctx.span_id


# =============================================================================
# 4. OpenTelemetry Collector Boundary & Buffer Queues
# =============================================================================
def test_collector_buffering_and_flush() -> None:
    """Verify collector buffering, queue accounting, and batch flush."""
    collector = OpenTelemetryCollectorBoundary(queue_capacity=50)

    # Ingest test span, metric, log
    span_ingested = collector.ingest_span({
        "name": "test_span",
        "stage": "api_trace",
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "span_id": "00f067aa0ba902b7",
    })
    metric_ingested = collector.ingest_metric({"name": "test_metric", "val": 1})
    log_ingested = collector.ingest_log({"message": "test log"})

    assert span_ingested is True
    assert metric_ingested is True
    assert log_ingested is True
    assert collector.queue_size == 3
    assert collector.dropped_total == 0

    flush_res = collector.flush()
    assert flush_res["success"] is True
    assert flush_res["exported_spans"] == 1
    assert flush_res["exported_metrics"] == 1
    assert flush_res["exported_logs"] == 1
    assert collector.queue_size == 0


# =============================================================================
# 5. Error Budget & Multi-Window Burn Rate Alerting
# =============================================================================
def test_error_budget_and_burn_rate_alerts() -> None:
    """Verify Google SRE multi-window burn rate alerts (1h @ 14.4x, 6h @ 6.0x)."""
    calculator = ErrorBudgetCalculator()

    # Case 1: Healthy system (99.8% on a 99.5% SLO) -> Zero alerts
    summary_healthy = calculator.evaluate_budget(
        sli_id="slo_directive_success_ratio",
        total_events=1000,
        bad_events=2,  # 0.2% error rate vs 0.5% allowed -> 40% budget consumed
    )
    assert summary_healthy.compliant is True
    assert summary_healthy.remaining_error_budget_percentage == 60.0
    assert len(summary_healthy.active_alerts) == 0

    # Case 2: Rapid Failure Burn (Fast 1h window: 10% error rate vs 0.5% allowed = 20x burn)
    summary_critical = calculator.evaluate_budget(
        sli_id="slo_directive_success_ratio",
        total_events=100,
        bad_events=10,  # 10% error rate
        window_events_1h=(100, 10),  # 20.0x burn rate in 1h window
    )
    assert summary_critical.compliant is False
    assert summary_critical.burn_rate_1h >= 14.4
    critical_alerts = [a for a in summary_critical.active_alerts if a.severity == AlertSeverity.CRITICAL]
    assert len(critical_alerts) == 1
    assert "Fast window 1h error budget burn rate" in critical_alerts[0].message
    assert summary_critical.exhaustion_forecast is not None


# =============================================================================
# 6. Observability Failure Injection & Safe Error Handling
# =============================================================================
def test_observability_failure_injection_fail_safe() -> None:
    """Prove observability failures do NOT crash or destabilize application workflows."""
    collector = get_collector()

    # Sub-test A: Collector Killed
    collector.set_alive(False)
    # App code ingests span: MUST NOT RAISE
    ingested = collector.ingest_span({"name": "test_span", "stage": "worker"})
    assert ingested is False
    assert collector.dropped_total >= 1
    health = check_observability_health()
    assert health.status == "CRITICAL"
    assert health.collector_alive is False

    # Restore Collector
    collector.set_alive(True)

    # Sub-test B: Collector Queue Overflow
    collector.set_force_overflow(True)
    ingested_ovf = collector.ingest_span({"name": "test_span_2", "stage": "worker"})
    assert ingested_ovf is False
    assert collector.queue_saturation_ratio == 1.0

    # Restore Overflow
    collector.set_force_overflow(False)

    # Sub-test C: Broken Exporter Connectivity
    collector.set_force_exporter_failure(True)
    flush_res = collector.flush()
    assert flush_res["success"] is False
    assert flush_res["reason"] == "exporter_connectivity_broken"
    assert collector.exporter_failures >= 1


# =============================================================================
# 7. Complete Governed Directive 12-Stage Trace Correlation & Exit Criteria
# =============================================================================
@pytest.mark.asyncio
async def test_complete_governed_directive_with_12_stage_correlation() -> None:
    """Execute live directive, prove 12-stage unbroken correlation, and answer all 11 exit questions."""
    harness = InstrumentedDirectiveExecutionHarness(tenant_id="tenant-certification-prod")

    report, disposition = await harness.execute_governed_directive(
        directive_text="Deploy enterprise multi-channel campaign with verified isolation",
        simulated_hitl_wait_seconds=0.15,
    )

    # 1. Verification of Report Verdict & SLO Invariant
    assert report.total_slos >= 12
    assert report.certification_verdict == "CERTIFIED"
    assert report.governing_slo_upheld is True
    assert report.observability_pipeline_completeness_ratio == 1.0

    # 2. Verification of 12 Required Stages
    rec = report.completeness_records[0]
    assert rec.complete is True
    assert len(rec.missing_stages) == 0
    assert len(rec.stages_seen) == 12
    assert rec.orphan_spans_count == 0

    expected_stages = [
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
    for s in expected_stages:
        assert s in rec.stages_seen

    # 3. Verification of All 11 Operator Exit-Criteria Questions Directly from Telemetry
    assert disposition.was_successful is True
    assert len(disposition.stage_latencies_seconds) == 12
    for stage_name, lat in disposition.stage_latencies_seconds.items():
        assert lat >= 0.0, f"Stage {stage_name} latency must be non-negative"

    # Stage consuming primary latency identified
    assert disposition.primary_latency_consumer in [s.value for s in expected_stages]

    # Retry status
    assert disposition.retry_executed is False

    # HITL bottleneck evaluated
    assert disposition.hitl_bottleneck in ["human_waiting", "system_processing", "none"]

    # Actuation count strictly 1
    assert disposition.actuation_count == 1
    assert disposition.exactly_once_actuation_guaranteed is True

    # Zero telemetry lost
    assert disposition.telemetry_lost_count == 0

    # Sandbox cgroup resources captured
    assert "cgroup_path" in disposition.sandbox_resources
    assert disposition.sandbox_resources["memory_limit_bytes"] == 256 * 1024 * 1024

    # W3C PROV audit chain intact
    assert disposition.prov_chain_length >= 1
    assert disposition.prov_root_record_hash is not None
    assert disposition.prov_root_record_hash.startswith("prov-sha256-")

    # Error budget & alert status
    assert disposition.error_budget_consumed is False
    assert disposition.operator_alert_triggered is False
