"""OpenTelemetry Distributed Tracing Subsystem with W3C Trace Context.

Preserves unbroken correlation across all 12 pipeline stages:
Frontend -> API -> IE/DAG -> Worker -> Sandbox -> Provisioner -> HITL -> Outbound -> Telemetry -> W_LEARN -> PROV -> CTS.
Integrates with OpenTelemetry TracerProvider and exports to the Collector boundary.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, AsyncGenerator, Generator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import Status, StatusCode, Tracer

from app.core.trace_context import W3CTraceContext
from app.observability.slo import ObservabilityPipelineStage

logger = logging.getLogger(__name__)

# Context variable tracking current active W3C Trace Context
_CURRENT_TRACE_CONTEXT: ContextVar[W3CTraceContext | None] = ContextVar(
    "current_trace_context", default=None
)

# Standard OpenTelemetry semantic attribute keys for Enterprise OS
ATTR_DIRECTIVE_ID = "enterprise_os.directive_id"
ATTR_TASK_ID = "enterprise_os.task_id"
ATTR_ATTEMPT_ID = "enterprise_os.attempt_id"
ATTR_EXECUTION_ID = "enterprise_os.execution_id"
ATTR_TENANT_ID = "enterprise_os.tenant_id"
ATTR_WORKER_ROLE = "enterprise_os.worker_role"
ATTR_PROV_ACTIVITY_ID = "enterprise_os.prov_activity_id"
ATTR_STAGE = "enterprise_os.stage"


class EnterpriseOSSpan:
    """Wrapper around trace span maintaining Enterprise OS correlation and timestamps."""

    def __init__(
        self,
        name: str,
        stage: ObservabilityPipelineStage | str,
        trace_context: W3CTraceContext,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.stage = stage.value if isinstance(stage, ObservabilityPipelineStage) else stage
        self.trace_context = trace_context
        self.attributes: dict[str, Any] = dict(attributes or {})
        self.start_time: float = time.time()
        self.end_time: float | None = None
        self.duration_seconds: float = 0.0
        self.status: str = "OK"
        self.error_message: str | None = None
        self.events: list[dict[str, Any]] = []

        # Standard correlation attributes
        self.attributes[ATTR_STAGE] = self.stage
        self.attributes["trace_id"] = trace_context.trace_id
        self.attributes["span_id"] = trace_context.span_id
        if trace_context.parent_span_id:
            self.attributes["parent_span_id"] = trace_context.parent_span_id

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": dict(attributes or {}),
        })

    def record_exception(self, exc: BaseException) -> None:
        self.status = "ERROR"
        self.error_message = str(exc)
        self.add_event("exception", {"exception.type": type(exc).__name__, "exception.message": str(exc)})

    def finish(self, status: str | None = None) -> None:
        if self.end_time is None:
            self.end_time = time.time()
            self.duration_seconds = self.end_time - self.start_time
        if status:
            self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "stage": self.stage,
            "trace_id": self.trace_context.trace_id,
            "span_id": self.trace_context.span_id,
            "parent_span_id": self.trace_context.parent_span_id,
            "traceparent": self.trace_context.traceparent,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "error_message": self.error_message,
            "attributes": self.attributes,
            "events": self.events,
        }


class EnterpriseOSTracer:
    """Manages span creation, W3C correlation propagation, and collector delivery."""

    def __init__(self, service_name: str = "enterprise_os") -> None:
        self.service_name = service_name
        self._provider = TracerProvider()
        trace.set_tracer_provider(self._provider)
        self._tracer: Tracer = trace.get_tracer(service_name, "1.0.0")

        # In-memory emitted spans buffer for observability pipeline integrity verification
        self._emitted_spans: list[EnterpriseOSSpan] = []

    def get_current_context(self) -> W3CTraceContext:
        ctx = _CURRENT_TRACE_CONTEXT.get()
        if ctx is None:
            ctx = W3CTraceContext.new()
            _CURRENT_TRACE_CONTEXT.set(ctx)
        return ctx

    def set_current_context(self, ctx: W3CTraceContext) -> None:
        _CURRENT_TRACE_CONTEXT.set(ctx)

    @contextlib.asynccontextmanager
    async def start_as_current_span(
        self,
        name: str,
        stage: ObservabilityPipelineStage | str,
        parent_context: W3CTraceContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> AsyncGenerator[EnterpriseOSSpan, None]:
        """Async context manager creating a correlated span with W3C propagation."""
        base_ctx = parent_context or _CURRENT_TRACE_CONTEXT.get()
        if base_ctx is None:
            child_ctx = W3CTraceContext.new()
        else:
            child_ctx = base_ctx.child_span()

        token = _CURRENT_TRACE_CONTEXT.set(child_ctx)
        span = EnterpriseOSSpan(name=name, stage=stage, trace_context=child_ctx, attributes=attributes)

        try:
            yield span
            span.finish(status="OK")
        except Exception as exc:
            span.record_exception(exc)
            span.finish(status="ERROR")
            raise
        finally:
            _CURRENT_TRACE_CONTEXT.reset(token)
            self._emitted_spans.append(span)
            with contextlib.suppress(Exception):
                from app.observability.collector import get_collector
                get_collector().ingest_span(span)

    @contextlib.contextmanager
    def start_span_sync(
        self,
        name: str,
        stage: ObservabilityPipelineStage | str,
        parent_context: W3CTraceContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[EnterpriseOSSpan, None, None]:
        """Synchronous context manager creating a correlated span."""
        base_ctx = parent_context or _CURRENT_TRACE_CONTEXT.get()
        if base_ctx is None:
            child_ctx = W3CTraceContext.new()
        else:
            child_ctx = base_ctx.child_span()

        token = _CURRENT_TRACE_CONTEXT.set(child_ctx)
        span = EnterpriseOSSpan(name=name, stage=stage, trace_context=child_ctx, attributes=attributes)

        try:
            yield span
            span.finish(status="OK")
        except Exception as exc:
            span.record_exception(exc)
            span.finish(status="ERROR")
            raise
        finally:
            _CURRENT_TRACE_CONTEXT.reset(token)
            self._emitted_spans.append(span)
            with contextlib.suppress(Exception):
                from app.observability.collector import get_collector
                get_collector().ingest_span(span)

    def get_emitted_spans(self, trace_id: str | None = None) -> list[EnterpriseOSSpan]:
        if trace_id is None:
            return list(self._emitted_spans)
        return [s for s in self._emitted_spans if s.trace_context.trace_id == trace_id]

    def clear(self) -> None:
        self._emitted_spans.clear()


# Global tracer singleton
_tracer_instance: EnterpriseOSTracer | None = None


def get_tracer() -> EnterpriseOSTracer:
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = EnterpriseOSTracer()
    return _tracer_instance
