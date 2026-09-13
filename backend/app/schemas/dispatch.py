"""Signed post-HITL execution directives.

A ``DispatchDirective`` is the only artifact the outbound actuation boundary
will act on; it must carry a valid signature over an approved action
preview before any external write is attempted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AudienceToken(BaseModel):
    """An opaque, cryptographically verifiable token authorizing post-HITL actuation toward a target audience/channel."""

    token_id: str
    target_audience: str
    tenant_id: str
    scope: str = "actuation"
    permitted_actions: list[str] = Field(default_factory=lambda: ["publish", "update", "deploy"])
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    issuer: str = "intelligence_engine"
    signature: str | None = None
    is_revoked: bool = False


class DispatchDirective(BaseModel):
    """A signed instruction to actuate an approved action preview."""

    dispatch_id: str
    task_id: str
    action_preview_id: str
    signature: str
    approved_by: str
    approved_at: datetime
    channel: str
    tenant_id: str = "default"
    audience: str = "global"
    audience_token: AudienceToken | str | None = None
    action_type: str = "publish"
    preview_content_hash: str | None = None
    clearance_id: str | None = None
    idempotency_key: str | None = None
    expires_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DispatchReadiness(BaseModel):
    """The outcome of MCP_ACT outbound validation certifying readiness for execution."""

    directive_id: str
    action_preview_id: str
    tenant_id: str
    channel: str
    status: str  # "READY", "REJECTED", "RATE_LIMITED", "REPLAY_DUPLICATE"
    is_ready: bool
    verified_clearance_id: str | None = None
    rate_limit_available: bool = True
    idempotent_cached: bool = False
    validation_notes: list[str] = Field(default_factory=list)
    certified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))