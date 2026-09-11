"""Signed post-HITL execution directives.

A ``DispatchDirective`` is the only artifact the outbound actuation boundary
will act on; it must carry a valid signature over an approved action
preview before any external write is attempted.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class DispatchDirective(BaseModel):
    """A signed instruction to actuate an approved action preview."""

    dispatch_id: str
    task_id: str
    action_preview_id: str
    signature: str
    approved_by: str
    approved_at: datetime
    channel: str
    payload: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))