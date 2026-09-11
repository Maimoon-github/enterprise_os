"""Persists normalized timeseries and conversion records."""
from __future__ import annotations

from app.schemas.telemetry import TelemetryEvent


class TelemetryRepository:
    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    def append(self, event: TelemetryEvent) -> None:
        self._events.append(event)

    def all(self) -> list[TelemetryEvent]:
        return list(self._events)
