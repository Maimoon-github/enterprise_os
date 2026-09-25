"""Authoritative schemas for durable institutional memory (MEM)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MemoryNamespace(StrEnum):
    """Namespaces for durable institutional knowledge."""

    BRAND_RULES = "brand_rules"
    ATTRIBUTION_HEURISTICS = "attribution_heuristics"
    REGULATORY_POLICIES = "regulatory_policies"
    NEGATIVE_CONSTRAINTS = "negative_constraints"
    PRODUCT_SPECS = "product_specs"
    GENERAL = "general"


class MemoryRecord(BaseModel):
    """A single piece of promoted, versioned, validated institutional knowledge."""

    memory_id: str
    tenant_id: str
    category: str
    statement: str
    confidence: float = Field(ge=0.0, le=1.0)
    namespace: str = "brand_rules"
    brand_id: str | None = None
    title: str = ""
    logical_id: str | None = None
    version: int = 1
    supersedes: str | None = None
    promoted_by: str = "system"
    promotion_justification: str = ""
    provenance_ref: str | None = None
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_task_ids: list[str] = Field(default_factory=list)
    promoted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
