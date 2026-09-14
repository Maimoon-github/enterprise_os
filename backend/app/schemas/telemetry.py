"""Normalized traffic, conversion, ad, social, and ROAS event contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TelemetryEventType(StrEnum):
    """The normalized categories of omnichannel performance events."""

    TRAFFIC = "traffic"
    CONVERSION = "conversion"
    AD_SPEND = "ad_spend"
    SOCIAL_ENGAGEMENT = "social_engagement"
    ROAS = "roas"
    ERROR = "error"


class TelemetrySourceType(StrEnum):
    """The supported transport / connector listener types."""

    WEBHOOK = "webhook"
    PIXEL = "pixel"
    CONVERSION = "conversion"
    EVENT_STREAM = "event_stream"
    ERROR_LOG = "error_log"


class TelemetrySurface(BaseModel):
    """An active omnichannel telemetry listening surface attached to a deployed channel."""

    channel: str
    source_type: TelemetrySourceType
    endpoint: str
    tenant_id: str
    account_id: str | None = None
    event_classes: list[TelemetryEventType] = Field(default_factory=list)
    is_active: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class TelemetryHandshakeProbe(BaseModel):
    """Result of a non-destructive handshake/synthetic connection validation probe."""

    channel: str
    source_type: TelemetrySourceType
    success: bool
    latency_ms: float = 0.0
    status: str = "ok"
    details: dict[str, Any] = Field(default_factory=dict)
    probed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OmnichannelTelemetryReadiness(BaseModel):
    """Authoritative readiness ledger documenting connected telemetry listeners."""

    readiness_id: str
    tenant_id: str
    is_ready: bool
    dependencies: dict[str, str] = Field(default_factory=dict)
    active_surfaces: list[TelemetrySurface] = Field(default_factory=list)
    probes: list[TelemetryHandshakeProbe] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    connected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WebhookIngestEnvelope(BaseModel):
    """Inbound transport-level telemetry event envelope."""

    tenant_id: str
    channel: str
    event_type: TelemetryEventType
    occurred_at: datetime
    account_id: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    signature: str | None = None
    idempotency_key: str | None = None


class TelemetryEvent(BaseModel):
    """A single normalized telemetry event ready for persistence and learning."""

    event_id: str
    tenant_id: str
    event_type: TelemetryEventType
    channel: str
    occurred_at: datetime
    metrics: dict[str, float] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))