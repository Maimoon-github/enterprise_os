"""W3C Trace Context and OpenTelemetry-compatible distributed tracing propagation.

Compliant with W3C Trace Context Level 1 Recommendation:
https://www.w3.org/TR/trace-context/
Format: version-trace_id-parent_id-trace_flags (e.g., 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

_TRACEPARENT_PATTERN = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)
_INVALID_TRACE_ID = "0" * 32
_INVALID_SPAN_ID = "0" * 16


@dataclass(frozen=True)
class W3CTraceContext:
    """Immutable W3C Trace Context value object."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    trace_flags: str = "01"
    version: str = "00"

    @property
    def traceparent(self) -> str:
        """Formatted W3C traceparent header string."""
        return f"{self.version}-{self.trace_id}-{self.span_id}-{self.trace_flags}"

    @classmethod
    def new(cls, *, trace_flags: str = "01") -> W3CTraceContext:
        """Generate a new root W3C trace context with cryptographically secure random IDs."""
        trace_id = os.urandom(16).hex()
        span_id = os.urandom(8).hex()
        return cls(trace_id=trace_id, span_id=span_id, trace_flags=trace_flags)

    @classmethod
    def parse(cls, header: str | None) -> W3CTraceContext | None:
        """Parse an incoming W3C traceparent header string.
        
        Returns None if header is missing, malformed, or has all-zero trace/span IDs.
        """
        if not header or not isinstance(header, str):
            return None
        cleaned = header.strip().lower()
        match = _TRACEPARENT_PATTERN.match(cleaned)
        if not match:
            return None
        version, trace_id, parent_id, trace_flags = match.groups()
        # Version 00 forward-compatibility check: cannot have all zeroes
        if trace_id == _INVALID_TRACE_ID or parent_id == _INVALID_SPAN_ID:
            return None
        return cls(
            version=version,
            trace_id=trace_id,
            span_id=parent_id,
            trace_flags=trace_flags,
        )

    def child_span(self) -> W3CTraceContext:
        """Create a child span context under this trace, preserving trace_id and trace_flags."""
        new_span_id = os.urandom(8).hex()
        return W3CTraceContext(
            version=self.version,
            trace_id=self.trace_id,
            span_id=new_span_id,
            parent_span_id=self.span_id,
            trace_flags=self.trace_flags,
        )

    def inject_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        """Inject traceparent into an existing or new HTTP header dictionary."""
        out = dict(headers or {})
        out["traceparent"] = self.traceparent
        return out

    def to_dict(self) -> dict[str, Any]:
        """Dictionary representation suitable for structured logs and provenance metadata."""
        return {
            "traceparent": self.traceparent,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "trace_flags": self.trace_flags,
        }
