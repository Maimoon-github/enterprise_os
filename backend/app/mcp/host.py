"""MCP host surface owned by the Intelligence Engine."""
from __future__ import annotations

from app.orchestration.intelligence_engine import IntelligenceEngine


class McpHost:
    def __init__(self, engine: IntelligenceEngine | None = None) -> None:
        self.engine = engine or IntelligenceEngine()

    def handle(self, message: dict) -> dict:
        return {"status": "acknowledged", "message_id": message.get("id")}
