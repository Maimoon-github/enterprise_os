"""Spend, claims, copy, and code-diff review dossiers for mandatory HITL review."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.governance import RiskLevel


class ActionPreviewKind(StrEnum):
    """The category of action a human reviewer is being asked to approve."""

    SPEND = "spend"
    CLAIM = "claim"
    COPY = "copy"
    CODE_DIFF = "code_diff"


class ActionPreview(BaseModel):
    """A human-reviewable dossier describing a proposed action before execution."""

    preview_id: str
    task_id: str
    kind: ActionPreviewKind
    summary: str
    diff: str | None = None
    spend_amount: float | None = Field(default=None, ge=0)
    risk_level: RiskLevel
    requires_approval: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))