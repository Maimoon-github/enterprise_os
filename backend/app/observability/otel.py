import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_tracer_initialized = False

def setup_telemetry(service_name: str = "marketing-os-backend"):
    global _tracer_initialized
    if _tracer_initialized:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
    environment = os.getenv("ENVIRONMENT", "development")

    resource = Resource.create({
        "service.name": service_name,
        "service.environment": environment,
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    _tracer_initialized = True

def get_tracer(name: str = "marketing-os-backend"):
    return trace.get_tracer(name)

__all__ = ["setup_telemetry", "get_tracer"]
