"""MCP host surface owned by the Intelligence Engine.

The Intelligence Engine is the sole owner of an ``McpHost`` instance; it is
the single point through which the IE reaches the data gateway (governed
RAG reads/writes) and the outbound gateway (post-HITL actuation), so no
other component needs its own reference to either gateway.
"""

from __future__ import annotations

from typing import Any

from app.mcp.data_gateway import DataGateway
from app.mcp.outbound_gateway import OutboundGateway
from app.schemas.dispatch import DispatchDirective
from app.security.authorization_boundary import CallerIdentity


class McpHost:
    """Aggregates the data and outbound gateways behind one host surface."""

    def __init__(self, data_gateway: DataGateway, outbound_gateway: OutboundGateway) -> None:
        self._data_gateway = data_gateway
        self._outbound_gateway = outbound_gateway

    async def query_data(
        self, caller: CallerIdentity, *, tenant_id: str, query: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """Route a governed read through the data gateway."""

        return await self._data_gateway.query(caller, tenant_id=tenant_id, query=query, top_k=top_k)

    async def ingest_data(
        self, caller: CallerIdentity, *, tenant_id: str, doc_id: str, text: str, source: str
    ) -> None:
        """Route a governed write through the data gateway."""

        await self._data_gateway.ingest(
            caller, tenant_id=tenant_id, doc_id=doc_id, text=text, source=source
        )

    async def actuate(self, dispatch: DispatchDirective) -> dict[str, str]:
        """Route a signed, approved dispatch through the outbound gateway."""

        return await self._outbound_gateway.execute(dispatch)

    async def query_memory(
        self, caller: CallerIdentity, *, tenant_id: str, category: str | None = None
    ) -> list[Any]:
        """Route an institutional memory query through the data gateway."""
        return await self._data_gateway.query_memory(caller, tenant_id=tenant_id, category=category)

    async def promote_memory(
        self, caller: CallerIdentity, *, tenant_id: str, record: Any
    ) -> None:
        """Route an institutional memory promotion through the data gateway."""
        await self._data_gateway.promote_memory(caller, tenant_id=tenant_id, record=record)

    async def resolve_artifact(
        self, caller: CallerIdentity, *, tenant_id: str, artifact_id: str
    ) -> Any:
        """Route an artifact resolution through the data gateway."""
        return await self._data_gateway.resolve_artifact(caller, tenant_id=tenant_id, artifact_id=artifact_id)

    async def register_artifact(
        self, caller: CallerIdentity, *, tenant_id: str, artifact: Any
    ) -> None:
        """Route an artifact registration through the data gateway."""
        await self._data_gateway.register_artifact(caller, tenant_id=tenant_id, artifact=artifact)

    async def read_cms_staged(
        self, caller: CallerIdentity, *, tenant_id: str, content_type: str
    ) -> list[dict[str, str]]:
        """Route a staged CMS query through the data gateway."""
        return await self._data_gateway.read_cms_staged(caller, tenant_id=tenant_id, content_type=content_type)

    async def apply_cms_changes(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        content_type: str,
        entry_id: str,
        diff: dict[str, str],
    ) -> dict[str, str]:
        """Route CMS changes through the data gateway."""
        return await self._data_gateway.apply_cms_changes(
            caller, tenant_id=tenant_id, content_type=content_type, entry_id=entry_id, diff=diff
        )