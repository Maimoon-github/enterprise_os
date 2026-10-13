"""Standard strategic initiative contracts conforming to engine specifications."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from src.schemas.evidence import EvidenceReference


class PriorityLevel(str, Enum):
    """Normalized priority assessment."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ApprovalStatus(str, Enum):
    """Lifecycle status assigned by Strategy Validator."""

    PROPOSED = "Proposed"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    REVISION_REQUESTED = "Revision_Requested"


class PriorityMatrix(BaseModel):
    """Mathematical prioritization matrix with ICE calculation."""

    impact: PriorityLevel = Field(..., description="Projected commercial impact")
    effort: PriorityLevel = Field(..., description="Implementation effort required")
    cost: PriorityLevel = Field(..., description="Financial investment required")
    confidence: str = Field(..., description="Percentage confidence rating, e.g., '92%'")
    ice_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Calculated ICE score (Impact * Confidence * Ease / 100)",
    )


class SuccessMetric(BaseModel):
    """Verifiable KPI metrics with baselines and targets."""

    kpi: str = Field(..., description="Target quantitative business metric")
    baseline: str = Field(..., description="Current observed baseline level")
    target: str = Field(..., description="Realistic target threshold")
    verification_source: str = Field(
        ...,
        description="Analytics platform to verify outcome (e.g. GA4, PostHog, Shopify Analytics)",
    )


class StrategicInitiative(BaseModel):
    """Unified data contract for all strategic recommendations."""

    recommendation_id: str = Field(
        ...,
        description="Format: REC-A-XXX or REC-B-XXX",
    )
    initiating_agent: str = Field(
        ...,
        description="Agent ID that created the initiative, e.g. 'Agent_5_Growth'",
    )
    finding: str = Field(
        ...,
        description="Observed empirical defect or opportunity",
    )
    evidence: EvidenceReference = Field(
        ...,
        description="Ground truth evidence reference",
    )
    business_implication: str = Field(
        ...,
        description="Quantified risk or unrealized opportunity",
    )
    actionable_prescription: str = Field(
        ...,
        description="Step-by-step remediation plan",
    )
    priority: PriorityMatrix = Field(
        ...,
        description="ICE-grounded priority matrix",
    )
    success_metric: SuccessMetric = Field(
        ...,
        description="Measurable KPI pair",
    )
    approval_status: ApprovalStatus = Field(
        default=ApprovalStatus.PROPOSED,
        description="Current verification status",
    )
    rejection_reasons: Optional[List[str]] = Field(
        default=None,
        description="Audit reasons if rejected by Agent 6",
    )
    iteration_cycle: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Revision loop count (max 3 before forced purge)",
    )
