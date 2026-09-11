"""Spend, claims, copy, and code-diff review dossiers."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PreviewKind(str, Enum):
    SPEND = "spend"
    CLAIMS = "claims"
    COPY = "copy"
    CODE = "code"


class ActionPreview(BaseModel):
    preview_id: str
    task_id: str
    tenant_id: str
    kind: PreviewKind
    summary: str
    diff: str | None = None
    spend: float | None = None


class ApprovalDecision(BaseModel):
    decision: str
    reviewer: str
    reason: str | None = None
    revisions: dict = Field(default_factory=dict)
