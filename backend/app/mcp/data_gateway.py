"""Governed CRUD facade between Agentic RAG and systems of record."""
from __future__ import annotations


class DataGateway:
    def read(self, entity: str, entity_id: str) -> dict | None:
        return None

    def write(self, entity: str, payload: dict) -> str:
        raise PermissionError("writes must flow through authorized dispatches")
