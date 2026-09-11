"""Schedules work according to the canonical dependency DAG."""
from __future__ import annotations

from app.schemas.governance import PolicyEnvelope


class DagScheduler:
    def plan(self, envelope: PolicyEnvelope) -> list[dict]:
        return [
            {"step": "context", "directive_id": envelope.directive_id},
            {"step": "workers", "directive_id": envelope.directive_id},
            {"step": "synthesis", "directive_id": envelope.directive_id},
            {"step": "hitl_preview", "directive_id": envelope.directive_id},
        ]
