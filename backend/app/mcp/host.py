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