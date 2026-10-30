import contextlib
import json
import logging
from collections.abc import Generator
from typing import Any

from app.core.config import settings
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import context, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger("observability.otel")

_tracer_initialized = False

# OpenInference Canonical Span Kinds
SPAN_KIND_AGENT = OpenInferenceSpanKindValues.AGENT.value
SPAN_KIND_CHAIN = OpenInferenceSpanKindValues.CHAIN.value
SPAN_KIND_LLM = OpenInferenceSpanKindValues.LLM.value
SPAN_KIND_TOOL = OpenInferenceSpanKindValues.TOOL.value
SPAN_KIND_RETRIEVER = OpenInferenceSpanKindValues.RETRIEVER.value
SPAN_KIND_RERANKER = OpenInferenceSpanKindValues.RERANKER.value
SPAN_KIND_GUARDRAIL = OpenInferenceSpanKindValues.GUARDRAIL.value
SPAN_KIND_EVALUATOR = OpenInferenceSpanKindValues.EVALUATOR.value
SPAN_KIND_DECISION = "DECISION"  # Extended OpenInference decision kind


def setup_telemetry(service_name: str | None = None) -> TracerProvider:
    """Initialize OpenTelemetry SDK with OpenInference conventions and OTLP export to Langfuse."""
    global _tracer_initialized
    if _tracer_initialized:
        return trace.get_tracer_provider()

    name = service_name or settings.OTEL_SERVICE_NAME
    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    env = getattr(settings, "ENVIRONMENT", "development")

    resource = Resource.create({
        "service.name": name,
        "service.environment": env,
        "telemetry.sdk.name": "opentelemetry",
        "telemetry.sdk.language": "python",
    })

    provider = TracerProvider(resource=resource)
    try:
        exporter = OTLPSpanExporter(endpoint=endpoint)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
    except Exception as exc:
        logger.warning("OTLP Span Exporter failed to bind to %s: %s. Continuing with in-memory provider.", endpoint, exc)

    trace.set_tracer_provider(provider)
    _tracer_initialized = True
    return provider


def get_tracer(name: str = "marketing-os") -> trace.Tracer:
    """Return active OpenTelemetry tracer."""
    return trace.get_tracer(name)


def sanitize_attribute_value(val: Any) -> str:
    """Safely convert payloads into JSON strings avoiding secret leakage."""
    if isinstance(val, (str, int, float, bool)) or val is None:
        return str(val) if val is not None else ""
    try:
        # Sanitize known sensitive keys if dict
        if isinstance(val, dict):
            clean = {k: ("***" if "secret" in k.lower() or "token" in k.lower() or "key" in k.lower() else v) for k, v in val.items()}
            return json.dumps(clean, default=str)
        return json.dumps(val, default=str)
    except Exception:
        return str(val)


@contextlib.contextmanager
def openinference_span(
    name: str,
    span_kind: str = SPAN_KIND_CHAIN,
    attributes: dict[str, Any] | None = None,
    input_value: Any = None,
    session_id: str | None = None,
) -> Generator[trace.Span, None, None]:
    """Context manager producing OpenInference-instrumented spans.

    Adheres strictly to OpenInference semantic conventions:
    - openinference.span.kind
    - session.id
    - input.value / output.value
    """
    tracer = get_tracer("marketing-os.openinference")
    with tracer.start_as_current_span(name) as span:
        kind_key = (
            SpanAttributes.OPENINFERENCE_SPAN_KIND.value
            if hasattr(SpanAttributes.OPENINFERENCE_SPAN_KIND, "value")
            else str(SpanAttributes.OPENINFERENCE_SPAN_KIND)
        )
        span.set_attribute(kind_key, span_kind)
        if session_id:
            sess_key = (
                SpanAttributes.SESSION_ID.value
                if hasattr(SpanAttributes.SESSION_ID, "value")
                else str(SpanAttributes.SESSION_ID)
            )
            span.set_attribute(sess_key, session_id)
        if input_value is not None:
            inp_key = (
                SpanAttributes.INPUT_VALUE.value
                if hasattr(SpanAttributes.INPUT_VALUE, "value")
                else str(SpanAttributes.INPUT_VALUE)
            )
            span.set_attribute(inp_key, sanitize_attribute_value(input_value))

        if attributes:
            for k, v in attributes.items():
                if v is not None:
                    span.set_attribute(k, sanitize_attribute_value(v) if isinstance(v, (dict, list)) else v)

        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            raise


def inject_trace_context(carrier: dict[str, str] | None = None) -> dict[str, str]:
    """Inject W3C traceparent context into carrier dict for distributed propagation."""
    out = dict(carrier or {})
    TraceContextTextMapPropagator().inject(out)
    return out


def extract_trace_context(carrier: dict[str, str]) -> context.Context:
    """Extract W3C traceparent context from carrier dict."""
    return TraceContextTextMapPropagator().extract(carrier)


__all__ = [
    "setup_telemetry",
    "get_tracer",
    "openinference_span",
    "inject_trace_context",
    "extract_trace_context",
    "SPAN_KIND_AGENT",
    "SPAN_KIND_CHAIN",
    "SPAN_KIND_LLM",
    "SPAN_KIND_TOOL",
    "SPAN_KIND_RETRIEVER",
    "SPAN_KIND_RERANKER",
    "SPAN_KIND_GUARDRAIL",
    "SPAN_KIND_EVALUATOR",
    "SPAN_KIND_DECISION",
]
