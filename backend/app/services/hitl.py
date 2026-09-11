"""Coordinates mandatory human approval and revision decisions."""
from __future__ import annotations

from app.schemas.action_preview import ApprovalDecision


class HitlService:
    def __init__(self) -> None:
        self._decisions: dict[str, ApprovalDecision] = {}

    def record(self, preview_id: str, decision: ApprovalDecision) -> None:
        self._decisions[preview_id] = decision

    def decision_for(self, preview_id: str) -> ApprovalDecision | None:
        return self._decisions.get(preview_id)
