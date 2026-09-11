"""Normalizes and persists omnichannel performance events."""
from __future__ import annotations

from app.schemas.telemetry import TelemetryEvent


class TelemetryService:
    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    def ingest(self, event: TelemetryEvent) -> None:
        self._events.append(event)

    def all(self) -> list[TelemetryEvent]:
        return list(self._events)
