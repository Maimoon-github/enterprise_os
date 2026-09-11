"""Normalized traffic, conversion, ad, social, and ROAS events."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TelemetryChannel(str, Enum):
    TRAFFIC = "traffic"
    CONVERSION = "conversion"
    AD = "ad"
    SOCIAL = "social"
    ROAS = "roas"


class TelemetryEvent(BaseModel):
    event_id: str
    tenant_id: str
    channel: TelemetryChannel
    occurred_at: datetime
    metrics: dict = Field(default_factory=dict)
    source: str | None = None
