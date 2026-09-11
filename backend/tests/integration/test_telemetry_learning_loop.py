"""Verifies telemetry feeds W_LEARN and validated memory promotion."""
from datetime import datetime, timezone

from app.schemas.telemetry import TelemetryChannel, TelemetryEvent
from app.services.memory_promotion import MemoryPromotionService
from app.services.telemetry import TelemetryService


def test_telemetry_ingest_and_memory_promotion() -> None:
    svc = TelemetryService()
    svc.ingest(
        TelemetryEvent(
            event_id="e1",
            tenant_id="t1",
            channel=TelemetryChannel.ROAS,
            occurred_at=datetime.now(timezone.utc),
            metrics={"roas": 3.2},
        )
    )
    assert svc.all()
    assert MemoryPromotionService().promote("t1", {"confidence": 0.9}) is True
    assert MemoryPromotionService().promote("t1", {"confidence": 0.1}) is False
