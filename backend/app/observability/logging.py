"""Structured JSON Logging with Automatic Trace Context & Correlation Propagation.

Injects W3C Trace Context (trace_id, span_id, traceparent) and Enterprise OS correlation
dimensions (directive_id, tenant_id, task_id, worker_role) into all log records.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.observability.tracing import (
    ATTR_DIRECTIVE_ID,
    ATTR_STAGE,
    ATTR_TASK_ID,
    ATTR_TENANT_ID,
    ATTR_WORKER_ROLE,
    get_tracer,
)


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects with trace correlation."""

    def format(self, record: logging.LogRecord) -> str:
        tracer = get_tracer()
        active_ctx = tracer.get_current_context()

        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject Trace Context if available
        if active_ctx:
            log_data["trace_id"] = active_ctx.trace_id
            log_data["span_id"] = active_ctx.span_id
            log_data["traceparent"] = active_ctx.traceparent

        # Inject extra attributes passed in record
        for key in (
            "directive_id",
            "tenant_id",
            "task_id",
            "attempt_id",
            "execution_id",
            "worker_role",
            "stage",
            "prov_activity_id",
        ):
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def configure_structured_logging(level: int = logging.INFO) -> None:
    """Configure root logger with StructuredJsonFormatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter())

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if reconfigured
    root.handlers = [handler]
