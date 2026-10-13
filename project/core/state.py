# pyright: reportMissingImports=false
"""LangGraph state schemas and transition reducers for Enterprise OS (TSK-02).
Deterministic state models with Pydantic v2 and LangGraph aggregation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage


class BrandProfile(BaseModel):
    """Pydantic model representing core brand identity and strategic guidelines."""

    brand_name: str
    tone_of_voice: List[str] = Field(default_factory=list)
    target_audience: str = ""
    core_pillars: List[str] = Field(
        default_factory=lambda: [
            "35% Educational",
            "25% Proof/Demos",
            "20% Brand Story",
            "20% Offers/Conversion",
        ]
    )
    guidelines: Dict[str, Any] = Field(default_factory=dict)
    learned_heuristics: List[str] = Field(default_factory=list)


BrandState = BrandProfile


class AuditMetrics(BaseModel):
    """Pydantic model for digital storefront, network, and commercial analytics."""

    reach: int = 0
    traffic: int = 0
    conversions: int = 0
    cac: float = 0.0
    clv: float = 0.0
    roas: float = 0.0
    bounce_rate: float = 0.0
    health_ratio: float = 0.0  # CLV / CAC (target >= 3.0)
    baymard_issues: List[str] = Field(default_factory=list)


AgentPhase = Literal[
    "init",
    "perception",
    "reasoning",
    "human_gate",
    "action",
    "evaluation",
    "completed",
]


class AgentState(TypedDict, total=False):
    """LangGraph agent state with operator.add reducers and phase transitions."""

    messages: Annotated[List[AnyMessage], operator.add]
    phase: AgentPhase
    brand_profile: Optional[BrandProfile]
    audit_metrics: Optional[AuditMetrics]
    task_queue: List[Dict[str, Any]]
    human_approved: Optional[bool]
    human_feedback: Optional[str]
    errors: Annotated[List[str], operator.add]
    artifacts: Annotated[List[str], operator.add]
    metadata: Dict[str, Any]
