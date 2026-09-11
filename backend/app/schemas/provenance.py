"""W3C PROV-inspired audit-event contracts.

Each record references the hash of the record immediately before it,
forming an append-only, tamper-evident chain per tenant.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ProvenanceRecord(BaseModel):
    """A single immutable entity/activity/agent audit-lineage entry."""

    record_id: str
    tenant_id: str
    entity_id: str
    activity: str
    agent: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    prev_record_hash: str | None = None
    record_hash: str