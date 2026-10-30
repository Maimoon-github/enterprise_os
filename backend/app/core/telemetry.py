from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from app.core.config import settings

def setup_telemetry():
    resource = Resource.create({
        "service.name": settings.OTEL_SERVICE_NAME,
        "service.environment": settings.ENVIRONMENT,
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

def get_tracer(name: str = "marketing_os"):
    return trace.get_tracer(name)
