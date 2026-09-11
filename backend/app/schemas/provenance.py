"""W3C PROV audit-event contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProvRecord(BaseModel):
    entity_id: str
    activity_id: str
    agent_id: str
    started_at: datetime
    ended_at: datetime | None = None
    attributes: dict = Field(default_factory=dict)
