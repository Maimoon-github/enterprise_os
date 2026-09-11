"""Provides the IE-exclusive bridge to Agentic RAG."""
from __future__ import annotations

from app.schemas.agent_contracts import ContextRequest


class RagQueryDispatcher:
    def __init__(self, controller=None) -> None:
        if controller is None:
            from app.services.rag.controller import RagController

            controller = RagController()
        self._controller = controller

    def dispatch(self, request: ContextRequest) -> dict:
        return self._controller.query(request.query, tenant_id=request.tenant_id)
