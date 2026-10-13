"""Validation schemas and audit trail contracts."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    """Individual verification gate assessment."""

    recommendation_id: str = Field(..., description="Target recommendation ID")
    check_type: str = Field(
        ...,
        description="provenance_check | logical_alignment | metric_feasibility",
    )
    passed: bool = Field(..., description="Whether the check succeeded")
    failure_reason: Optional[str] = Field(
        default=None,
        description="Detailed diagnosis if check failed",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC time of verification step",
    )


class ValidationReport(BaseModel):
    """Aggregate adversarial review ledger."""

    status: str = Field(
        default="Pending",
        description="Pending | Approved | Revision_Requested | Failed",
    )
    total_audited: int = Field(default=0, description="Total initiatives evaluated")
    passed_count: int = Field(default=0, description="Number of fully approved initiatives")
    failed_count: int = Field(default=0, description="Number of rejected initiatives")
    audit_trail: List[AuditEntry] = Field(
        default_factory=list,
        description="Ordered sequence of audit logs",
    )
