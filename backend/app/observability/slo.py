"""Enterprise OS Service Level Objectives (SLO) & Indicators (SLI) Registry.

Defines formal, measurable SLO targets, mathematical SLI formulations, error budget definitions,
and the critical Observability-Pipeline Integrity SLO (>= 99.99% telemetry completeness).
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime, timedelta
from typing import Any
from pydantic import BaseModel, Field


class SLOCategory(str, enum.Enum):
    """Categorical domain for Enterprise OS production SLOs."""

    DIRECTIVE = "directive"
    SANDBOX = "sandbox"
    HITL = "hitl"
    OUTBOUND = "outbound"
    TELEMETRY = "telemetry"
    DATABASE_DR = "database_dr"
    OBSERVABILITY_PIPELINE = "observability_pipeline"


class SLIComparison(str, enum.Enum):
    """Direction of comparison for determining compliance."""

    GREATER_THAN_OR_EQUAL = "gte"  # Ratio >= target (e.g., success ratio >= 99.5%)
    LESS_THAN_OR_EQUAL = "lte"     # Metric <= target (e.g., latency p99 <= 5.0s, RTO <= 15s)


class SLIDefinition(BaseModel):
    """Formal definition of a Service Level Indicator and associated Objective."""

    sli_id: str
    name: str
    category: SLOCategory
    description: str
    target_value: float  # e.g., 99.5 (%) or 5.0 (seconds)
    comparison: SLIComparison = SLIComparison.GREATER_THAN_OR_EQUAL
    unit: str = "%"  # "%", "s", "ms"
    window_seconds: int = 3600  # Default 1-hour evaluation window
    is_critical: bool = True


class SLIEvaluationResult(BaseModel):
    """Result of an instantaneous or windowed SLI evaluation."""

    sli_id: str
    name: str
    category: SLOCategory
    target_value: float
    actual_value: float
    comparison: SLIComparison
    compliant: bool
    unit: str
    good_events: int = 0
    total_events: int = 0
    error_budget_percentage: float = 0.0
    error_budget_consumed_percentage: float = 0.0
    burn_rate_1h: float = 0.0
    burn_rate_6h: float = 0.0
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = Field(default_factory=dict)


class ObservabilityPipelineStage(str, enum.Enum):
    """The mandatory 12-stage correlation journey for every governed directive."""

    FRONTEND_REQ = "frontend_request"
    API_TRACE = "api_trace"
    IE_DAG = "ie_dag"
    WORKER = "worker"
    SANDBOX_MANDATE = "sandbox_mandate"
    PROVISIONER_RUNTIME = "provisioner_runtime"
    HITL = "hitl"
    OUTBOUND_DISPATCH = "outbound_dispatch"
    TELEMETRY = "telemetry"
    W_LEARN = "w_learn"
    PROV = "prov"
    TERMINAL_CTS = "terminal_cts"


class ObservabilityCompletenessRecord(BaseModel):
    """Record verifying end-to-end telemetry and trace completeness for a single directive."""

    directive_id: str
    tenant_id: str
    root_trace_id: str
    stages_seen: list[ObservabilityPipelineStage] = Field(default_factory=list)
    missing_stages: list[ObservabilityPipelineStage] = Field(default_factory=list)
    orphan_spans_count: int = 0
    dropped_telemetry_count: int = 0
    cardinality_violations_count: int = 0
    missing_correlation_ids: list[str] = Field(default_factory=list)
    complete: bool = False
    completeness_ratio: float = 0.0
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProductionSLORegistry:
    """Canonical registry holding all certified Enterprise OS SLO targets."""

    STANDARD_SLOS: list[SLIDefinition] = [
        # 1. Directive Completion & Latency
        SLIDefinition(
            sli_id="slo_directive_success_ratio",
            name="Directive Success Ratio",
            category=SLOCategory.DIRECTIVE,
            description="Proportion of submitted directives that terminate in valid terminal state without fatal unhandled error",
            target_value=99.5,
            comparison=SLIComparison.GREATER_THAN_OR_EQUAL,
            unit="%",
        ),
        SLIDefinition(
            sli_id="slo_directive_completion_latency_p95",
            name="Directive Latency p95",
            category=SLOCategory.DIRECTIVE,
            description="95th percentile wall time for complete directive orchestration lifecycle",
            target_value=30.0,
            comparison=SLIComparison.LESS_THAN_OR_EQUAL,
            unit="s",
        ),
        # 2. Specialist Sandbox Provisioning & Execution
        SLIDefinition(
            sli_id="slo_sandbox_provisioning_latency_p99",
            name="Sandbox Provisioning Latency p99",
            category=SLOCategory.SANDBOX,
            description="99th percentile time to allocate cgroups, mount namespaces, and initialize physical sandbox runtime",
            target_value=2.0,
            comparison=SLIComparison.LESS_THAN_OR_EQUAL,
            unit="s",
        ),
        SLIDefinition(
            sli_id="slo_sandbox_execution_latency_p99",
            name="Sandbox Specialist Execution Latency p99",
            category=SLOCategory.SANDBOX,
            description="99th percentile execution time for bounded specialist execution inside physical sandbox",
            target_value=5.0,
            comparison=SLIComparison.LESS_THAN_OR_EQUAL,
            unit="s",
        ),
        # 3. HITL Timing (Separating Human Waiting from Processing Window)
        SLIDefinition(
            sli_id="slo_hitl_processing_latency_p99",
            name="HITL System Processing Latency p99",
            category=SLOCategory.HITL,
            description="99th percentile internal latency for dossier assembly, cryptographic validation, and signature verification",
            target_value=0.5,
            comparison=SLIComparison.LESS_THAN_OR_EQUAL,
            unit="s",
        ),
        SLIDefinition(
            sli_id="slo_hitl_waiting_window_compliance",
            name="HITL Waiting Window Compliance",
            category=SLOCategory.HITL,
            description="Proportion of approvals reviewed within SLA before mandatory timeout/fail-closed trigger",
            target_value=99.0,
            comparison=SLIComparison.GREATER_THAN_OR_EQUAL,
            unit="%",
        ),
        # 4. Outbound Actuation
        SLIDefinition(
            sli_id="slo_outbound_actuation_zero_duplicate",
            name="Outbound Zero Duplicate Guarantee",
            category=SLOCategory.OUTBOUND,
            description="100% mathematical guarantee that no outbound dispatch results in duplicated external platform mutation",
            target_value=100.0,
            comparison=SLIComparison.GREATER_THAN_OR_EQUAL,
            unit="%",
        ),
        SLIDefinition(
            sli_id="slo_outbound_actuation_latency_p95",
            name="Outbound Actuation Latency p95",
            category=SLOCategory.OUTBOUND,
            description="95th percentile latency from HITL approval seal to external platform response acknowledgement",
            target_value=3.0,
            comparison=SLIComparison.LESS_THAN_OR_EQUAL,
            unit="s",
        ),
        # 5. Telemetry Intake
        SLIDefinition(
            sli_id="slo_telemetry_ingestion_lag_p95",
            name="Telemetry Ingestion Lag p95",
            category=SLOCategory.TELEMETRY,
            description="95th percentile duration between receipt admission and work item completion",
            target_value=2.0,
            comparison=SLIComparison.LESS_THAN_OR_EQUAL,
            unit="s",
        ),
        # 6. Database Availability & DR
        SLIDefinition(
            sli_id="slo_database_pitr_rpo",
            name="PostgreSQL PITR RPO Conformance",
            category=SLOCategory.DATABASE_DR,
            description="Recovery Point Objective maximum allowed data loss window",
            target_value=1.0,
            comparison=SLIComparison.LESS_THAN_OR_EQUAL,
            unit="s",
        ),
        SLIDefinition(
            sli_id="slo_database_pitr_rto",
            name="PostgreSQL PITR RTO Conformance",
            category=SLOCategory.DATABASE_DR,
            description="Recovery Time Objective maximum allowed clean-host recovery duration",
            target_value=15.0,
            comparison=SLIComparison.LESS_THAN_OR_EQUAL,
            unit="s",
        ),
        # 7. OBSERVABILITY-PIPELINE INTEGRITY SLO (CRITICAL INVARIANT)
        SLIDefinition(
            sli_id="slo_observability_pipeline_completeness",
            name="Observability-Pipeline Integrity & Completeness",
            category=SLOCategory.OBSERVABILITY_PIPELINE,
            description="Proportion of governed directives maintaining complete 12-stage unbroken trace/telemetry correlation without orphan spans, drops, or missing correlation IDs",
            target_value=99.99,
            comparison=SLIComparison.GREATER_THAN_OR_EQUAL,
            unit="%",
            window_seconds=3600,
        ),
    ]

    def __init__(self) -> None:
        self._definitions: dict[str, SLIDefinition] = {
            d.sli_id: d for d in self.STANDARD_SLOS
        }

    def get(self, sli_id: str) -> SLIDefinition | None:
        return self._definitions.get(sli_id)

    def list_all(self) -> list[SLIDefinition]:
        return list(self._definitions.values())

    def list_by_category(self, category: SLOCategory) -> list[SLIDefinition]:
        return [d for d in self._definitions.values() if d.category == category]
