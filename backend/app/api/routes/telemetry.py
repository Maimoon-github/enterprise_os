"""Receives webhook, conversion, pixel, and event telemetry."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.schemas.telemetry import TelemetryEvent
from app.services.telemetry import TelemetryService

router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest(event: TelemetryEvent) -> dict[str, str]:
    TelemetryService().ingest(event)
    return {"status": "ingested", "event_id": event.event_id}
