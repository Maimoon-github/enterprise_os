"""Production Observability, OpenTelemetry Collector & SLO Certification Package."""

from app.observability.collector import (
    CollectorExporterError,
    CollectorQueueSaturationError,
    OpenTelemetryCollectorBoundary,
    get_collector,
)
from app.observability.error_budget import (
    AlertSeverity,
    BurnRateAlert,
    ErrorBudgetCalculator,
    ErrorBudgetSummary,
)
from app.observability.health import (
    ObservabilityHealthReport,
    ObservabilityPipelineIntegrityEvaluator,
    check_observability_health,
)
from app.observability.logging import (
    StructuredJsonFormatter,
    configure_structured_logging,
)
from app.observability.metrics import (
    ALLOWED_METRIC_DIMENSIONS,
    CardinalityProtector,
    EnterpriseOSMetrics,
    FORBIDDEN_METRIC_DIMENSIONS,
    get_metrics,
)
from app.observability.slo import (
    ObservabilityCompletenessRecord,
    ObservabilityPipelineStage,
    ProductionSLORegistry,
    SLIComparison,
    SLIDefinition,
    SLIEvaluationResult,
    SLOCategory,
)
from app.observability.slo_evaluator import (
    ObservabilityTelemetryDisposition,
    ProductionSLOEvaluator,
    SLOCertificationReport,
)
from app.observability.directive_runner import (
    InstrumentedDirectiveExecutionHarness,
)
from app.observability.tracing import (
    ATTR_ATTEMPT_ID,
    ATTR_DIRECTIVE_ID,
    ATTR_EXECUTION_ID,
    ATTR_PROV_ACTIVITY_ID,
    ATTR_STAGE,
    ATTR_TASK_ID,
    ATTR_TENANT_ID,
    ATTR_WORKER_ROLE,
    EnterpriseOSSpan,
    EnterpriseOSTracer,
    get_tracer,
)

__all__ = [
    "ALLOWED_METRIC_DIMENSIONS",
    "ATTR_ATTEMPT_ID",
    "ATTR_DIRECTIVE_ID",
    "ATTR_EXECUTION_ID",
    "ATTR_PROV_ACTIVITY_ID",
    "ATTR_STAGE",
    "ATTR_TASK_ID",
    "ATTR_TENANT_ID",
    "ATTR_WORKER_ROLE",
    "AlertSeverity",
    "BurnRateAlert",
    "CardinalityProtector",
    "CollectorExporterError",
    "CollectorQueueSaturationError",
    "EnterpriseOSMetrics",
    "EnterpriseOSSpan",
    "EnterpriseOSTracer",
    "ErrorBudgetCalculator",
    "ErrorBudgetSummary",
    "FORBIDDEN_METRIC_DIMENSIONS",
    "InstrumentedDirectiveExecutionHarness",
    "ObservabilityCompletenessRecord",
    "ObservabilityHealthReport",
    "ObservabilityPipelineIntegrityEvaluator",
    "ObservabilityPipelineStage",
    "ObservabilityTelemetryDisposition",
    "OpenTelemetryCollectorBoundary",
    "ProductionSLOEvaluator",
    "ProductionSLORegistry",
    "SLOCertificationReport",
    "SLIComparison",
    "SLIDefinition",
    "SLIEvaluationResult",
    "SLOCategory",
    "StructuredJsonFormatter",
    "check_observability_health",
    "configure_structured_logging",
    "get_collector",
    "get_metrics",
    "get_tracer",
]
