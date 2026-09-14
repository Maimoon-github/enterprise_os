"""Normalizes and persists omnichannel performance events."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.persistence.repositories.telemetry import TelemetryRepository
from app.schemas.telemetry import TelemetryEvent, TelemetryEventType


class TelemetryNormalizer:
    """Normalizes raw webhook/pixel/event payloads into ``TelemetryEvent`` records."""

    def __init__(
        self,
        repository: TelemetryRepository,
        data_gateway: Any | None = None,
    ) -> None:
        self._repository = repository
        self._data_gateway = data_gateway

    def normalize(
        self,
        *,
        tenant_id: str,
        event_type: TelemetryEventType,
        channel: str,
        occurred_at: datetime,
        metrics: dict[str, float],
        event_id: str | None = None,
        source_id: str | None = None,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
        payload: dict[str, Any] | None = None,
        dimensions: dict[str, str] | None = None,
    ) -> TelemetryEvent:
        """Build a normalized ``TelemetryEvent`` from raw fields."""

        return TelemetryEvent(
            event_id=event_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
            event_type=event_type,
            channel=channel,
            occurred_at=occurred_at,
            metrics=metrics,
            source_id=source_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            payload=payload or {},
            dimensions=dimensions or {},
        )

    async def ingest(
        self,
        *,
        tenant_id: str,
        event_type: TelemetryEventType,
        channel: str,
        occurred_at: datetime,
        metrics: dict[str, float],
        event_id: str | None = None,
        source_id: str | None = None,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
        payload: dict[str, Any] | None = None,
        dimensions: dict[str, str] | None = None,
    ) -> TelemetryEvent:
        """Normalize and persist a raw telemetry payload, returning the stored event."""

        event = self.normalize(
            tenant_id=tenant_id,
            event_type=event_type,
            channel=channel,
            occurred_at=occurred_at,
            metrics=metrics,
            event_id=event_id,
            source_id=source_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            payload=payload,
            dimensions=dimensions,
        )

        if self._data_gateway is not None and hasattr(self._data_gateway, "record_telemetry"):
            from app.schemas.governance import RiskLevel, TenantScope
            from app.security.authorization_boundary import CallerIdentity

            caller = CallerIdentity(
                subject="telemetry_engine",
                tenant_scope=TenantScope(tenant_id=tenant_id),
                risk_ceiling=RiskLevel.LOW,
            )
            await self._data_gateway.record_telemetry(caller, tenant_id=tenant_id, event=event)
        else:
            await self._repository.record(event)

        return event

    async def for_learning_loop(self, tenant_id: str) -> list[TelemetryEvent]:
        """Return ROAS events feeding W_LEARN's attribution and decay analysis."""

        return await self._repository.list_by_type(tenant_id, TelemetryEventType.ROAS.value)