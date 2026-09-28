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

        if self._data_gateway is not None and hasattr(self._data_gateway, "list_telemetry"):
            from app.schemas.governance import RiskLevel, TenantScope
            from app.security.authorization_boundary import CallerIdentity

            caller = CallerIdentity(
                subject="telemetry_engine",
                tenant_scope=TenantScope(tenant_id=tenant_id),
                risk_ceiling=RiskLevel.LOW,
            )
            return await self._data_gateway.list_telemetry(
                caller, tenant_id=tenant_id, event_type=TelemetryEventType.ROAS.value
            )
        return await self._repository.list_by_type(tenant_id, TelemetryEventType.ROAS.value)

    async def admit(
        self,
        record: Any,
        *,
        session: Any = None,
    ) -> Any:
        """Validate, scrub, and durably admit a telemetry record, returning an opaque receipt."""
        if hasattr(record, "model_dump"):
            rec_dict = record.model_dump(mode="json")
        else:
            rec_dict = dict(record)

        tenant_id = rec_dict.get("tenant_id")
        if not tenant_id or not str(tenant_id).strip():
            raise ValueError("Tenant ID is required for telemetry admission.")

        from app.services.telemetry_engine import scrub_sensitive_telemetry
        if isinstance(rec_dict.get("payload"), dict):
            rec_dict["payload"] = scrub_sensitive_telemetry(rec_dict["payload"])

        channel = rec_dict.get("channel")
        if rec_dict.get("trust_class") == "browser_untrusted":
            if isinstance(rec_dict.get("payload"), dict):
                rec_dict["payload"]["is_authoritative_order"] = False

        if self._data_gateway is not None and hasattr(self._data_gateway, "admit"):
            from app.schemas.governance import RiskLevel, TenantScope
            from app.security.authorization_boundary import CallerIdentity

            caller = CallerIdentity(
                subject="telemetry_service",
                tenant_scope=TenantScope(tenant_id=tenant_id),
                risk_ceiling=RiskLevel.LOW,
                allowed_capabilities=frozenset({"telemetry.ingest", "mcp_data_write"}),
            )
            receipt = await self._data_gateway.admit(caller, tenant_id=tenant_id, record=rec_dict, session=session)
        else:
            receipt = await self._repository.admit(rec_dict, session=session)

        if channel and hasattr(receipt, "channel"):
            receipt.channel = channel
        return receipt



TelemetryService = TelemetryNormalizer