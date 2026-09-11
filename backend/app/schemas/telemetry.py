"""Normalized traffic, conversion, ad, social, and ROAS event contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class TelemetryEventType(StrEnum):
    """The normalized categories of omnichannel performance events."""

    TRAFFIC = "traffic"
    CONVERSION = "conversion"
    AD_SPEND = "ad_spend"
    SOCIAL_ENGAGEMENT = "social_engagement"
    ROAS = "roas"


class TelemetryEvent(BaseModel):
    """A single normalized telemetry event ready for persistence and learning."""

    event_id: str
    tenant_id: str
    event_type: TelemetryEventType
    channel: str
    occurred_at: datetime
    metrics: dict[str, float] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))