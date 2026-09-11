"""Receives webhook, conversion, pixel, and event telemetry."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.schemas.telemetry import TelemetryEvent, TelemetryEventType

router = APIRouter()


class TelemetryIngestRequest(BaseModel):
    """The transport-layer shape of an incoming raw telemetry event."""

    tenant_id: str
    event_type: TelemetryEventType
    channel: str
    occurred_at: datetime
    metrics: dict[str, float]


@router.post("", response_model=TelemetryEvent, status_code=201)
async def ingest_telemetry(payload: TelemetryIngestRequest, request: Request) -> TelemetryEvent:
    """Normalize and persist an incoming telemetry event."""

    telemetry_normalizer = request.app.state.telemetry_normalizer
    return await telemetry_normalizer.ingest(
        tenant_id=payload.tenant_id,
        event_type=payload.event_type,
        channel=payload.channel,
        occurred_at=payload.occurred_at,
        metrics=payload.metrics,
    )