"""Builds policy-screened context slices for workers."""
from __future__ import annotations

from app.schemas.agent_contracts import ContextRequest


class ContextAssembler:
    def build(self, request: ContextRequest, allowed_scopes: set[str]) -> dict:
        scopes = [s for s in request.scopes if s in allowed_scopes]
        return {"request_id": request.request_id, "scopes": scopes, "query": request.query}
