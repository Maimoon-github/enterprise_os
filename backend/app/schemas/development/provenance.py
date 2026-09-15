"""Provenance tracking models for development artifacts and sub-agent transitions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DevelopmentProvenanceRecord(BaseModel):
    """Immutable audit record binding sub-agent execution to sandbox evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str
    task_id: str
    step_id: str
    agent_id: str
    input_hash: str
    output_hash: str
    sandbox_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
