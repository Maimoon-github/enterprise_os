"""Verifies telemetry feeds W_LEARN and validated memory promotion."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.agents.learning_performance import LearningPerformanceAgent
from app.persistence.repositories.memory import MemoryRepository
from app.persistence.repositories.telemetry import TelemetryRepository
from app.schemas.agent_contracts import TaskGrant
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.telemetry import TelemetryEventType
from app.services.memory_promotion import MemoryPromotionService
from app.services.telemetry import TelemetryNormalizer
from tests.conftest import FakeSandboxClient


class _InMemoryTelemetryRepository(TelemetryRepository):
    """An in-memory stand-in for the JSONB-backed telemetry repository."""

    # Intentionally bypasses DB init; every inherited method is overridden below.
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def record(self, event) -> None:  # type: ignore[override]
        self._store[event.event_id] = event

    async def list_by_type(self, tenant_id: str, event_type: str) -> list:  # type: ignore[override]
        return [
            event
            for event in self._store.values()
            if event.tenant_id == tenant_id and event.event_type.value == event_type
        ]


class _InMemoryMemoryRepository(MemoryRepository):
    """An in-memory stand-in for the JSONB-backed institutional memory repository."""

    # Intentionally bypasses DB init; every inherited method is overridden below.
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def promote(self, record) -> None:  # type: ignore[override]
        self._store[record.memory_id] = record

    async def list_by_tenant(self, tenant_id: str, category: str | None = None) -> list:
        records = [r for r in self._store.values() if getattr(r, "tenant_id", None) == tenant_id]
        if category:
            records = [r for r in records if getattr(r, "category", None) == category]
        return records

    def all(self) -> list:
        return list(self._store.values())


@pytest.mark.asyncio
async def test_roas_telemetry_feeds_learning_performance_worker() -> None:
    telemetry_repository = _InMemoryTelemetryRepository()
    normalizer = TelemetryNormalizer(telemetry_repository)

    await normalizer.ingest(
        tenant_id="acme",
        event_type=TelemetryEventType.ROAS,
        channel="meta",
        occurred_at=datetime.now(UTC),
        metrics={"roas": 3.2},
    )
    await normalizer.ingest(
        tenant_id="acme",
        event_type=TelemetryEventType.TRAFFIC,
        channel="meta",
        occurred_at=datetime.now(UTC),
        metrics={"sessions": 100},
    )

    roas_events = await normalizer.for_learning_loop("acme")
    assert len(roas_events) == 1
    assert roas_events[0].metrics["roas"] == 3.2

    fake_sandbox = FakeSandboxClient()
    agent = LearningPerformanceAgent(fake_sandbox)
    grant = TaskGrant(
        task_id="task-learn-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC),
    )
    envelope = await agent.run(grant, context={"roas_events": roas_events})
    assert envelope.evidence  # the worker produced evidence from the sandbox output


@pytest.mark.asyncio
async def test_memory_promotion_requires_minimum_confidence() -> None:
    memory_repository = _InMemoryMemoryRepository()
    service = MemoryPromotionService(memory_repository, min_confidence=0.7)

    below_threshold = await service.promote(
        tenant_id="acme",
        category="attribution",
        statement="Meta drives higher last-click conversions than TikTok.",
        confidence=0.5,
        source_task_ids=["task-learn-1"],
    )
    assert below_threshold is None
    assert memory_repository.all() == []

    above_threshold = await service.promote(
        tenant_id="acme",
        category="attribution",
        statement="Meta drives higher last-click conversions than TikTok.",
        confidence=0.85,
        source_task_ids=["task-learn-1"],
    )
    assert above_threshold is not None
    assert len(memory_repository.all()) == 1