"""Bounded task grants, context requests, evidence envelopes, and confidence data."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TaskGrant(BaseModel):
    grant_id: str
    worker_id: str
    tenant_id: str
    capabilities: list[str]
    budget_ceiling: float = Field(ge=0.0)
    expires_at: str


class ContextRequest(BaseModel):
    request_id: str
    worker_id: str
    tenant_id: str
    query: str
    scopes: list[str] = Field(default_factory=list)


class EvidenceEnvelope(BaseModel):
    worker_id: str
    task_id: str
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[str] = Field(default_factory=list)
