"""Cryptographically bindable approval token schemas for development workflow steps."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DevelopmentApprovalToken(BaseModel):
    """Cryptographic approval token binding a human decision to exact input/output artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str
    task_id: str
    step_id: str
    subagent_id: str
    decision: Literal["APPROVE", "REJECT", "REQUEST_REVISION"]
    input_snapshot_hash: str = Field(min_length=32)
    output_snapshot_hash: str = Field(min_length=32)
    review_dossier_hash: str = Field(min_length=32)
    policy_version: str = "1.0.0"
    reviewer_identity: str
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    signature: str = Field(min_length=32)
