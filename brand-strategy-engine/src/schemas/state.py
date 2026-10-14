"""Unified state contracts for Universal AI Brand Strategy Engine."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.schemas.evidence import EvidenceReference
from src.schemas.initiative import StrategicInitiative
from src.schemas.validation import ValidationReport


class ReActStep(BaseModel):
    """Typed Pydantic execution trace record for deterministic Reason-Act-Observe-Reflect cycles."""

    step: int = Field(..., description="1-indexed execution step number")
    thought: str = Field(..., description="Reasoning / hypothesis behind the step")
    action: str = Field(..., description="Tool or action invoked")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments passed to action")
    observation: str = Field(default="", description="Observed outcome or tool output")
    reflection: str = Field(default="", description="Post-observation reflection and state evaluation")
    error: Optional[str] = Field(default=None, description="Error encountered during execution, if any")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class OperationalMode(str, Enum):
    """Operational modality for the engine."""

    MODE_A_PERSONAL = "Mode_A_Personal"
    MODE_B_ECOMMERCE = "Mode_B_eCommerce"


class AnalystSlice(BaseModel):
    """Bounded state slice injected into Agent 1 (Analyst)."""

    website_url: str = Field(..., description="Target brand root URL")
    mode: str = Field(..., description="Operational modality")
    business_goals: List[str] = Field(default_factory=list, description="Commercial goals")
    industry: str = Field(..., description="Industry vertical")


class AudienceSlice(BaseModel):
    """Bounded state slice injected into Agent 2 (Audience Strategist)."""

    mode: str = Field(..., description="Operational modality")
    industry: str = Field(..., description="Industry vertical")
    target_market: List[str] = Field(default_factory=list, description="Target customer segments")
    observation_notes: str = Field(default="", description="Visual and touchpoint observation notes")
    business_goals: List[str] = Field(default_factory=list, description="Commercial goals")
    competitors: List[Dict[str, Any]] = Field(default_factory=list, description="Competitor profiles")


class BrandSlice(BaseModel):
    """Bounded state slice injected into Agent 3 (Brand Strategist)."""

    mode: str = Field(..., description="Operational modality")
    headline: str = Field(default="", description="Extracted hero headline copy")
    brand_name: str = Field(..., description="Target brand name")
    audience_icp: Dict[str, Any] = Field(default_factory=dict, description="ICP model from Agent 2")
    competitors: List[Dict[str, Any]] = Field(default_factory=list, description="Competitor profiles")


class SEOSlice(BaseModel):
    """Bounded state slice injected into Agent 4 (SEO & Content Strategist)."""

    mode: str = Field(..., description="Operational modality")
    website_url: str = Field(..., description="Target website URL")
    dom_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Captured DOM metadata and hierarchy")
    brand_positioning: Dict[str, Any] = Field(default_factory=dict, description="Synthesized brand positioning")


class GrowthSlice(BaseModel):
    """Bounded state slice injected into Agent 5 (Growth Strategist)."""

    mode: str = Field(..., description="Operational modality")
    website_url: str = Field(..., description="Target website URL")
    audience_analysis: Dict[str, Any] = Field(default_factory=dict, description="Audience analysis")
    brand_positioning: Dict[str, Any] = Field(default_factory=dict, description="Brand positioning")
    seo_and_content_plan: Dict[str, Any] = Field(default_factory=dict, description="SEO and content blueprint")
    visual_evidence_vnc: List[EvidenceReference] = Field(default_factory=list, description="Empirical visual evidence")
    business_goals: List[str] = Field(default_factory=list, description="Commercial goals")


class ValidatorSlice(BaseModel):
    """Bounded state slice injected into Agent 6 (Strategy Validator)."""

    growth_initiatives: List[StrategicInitiative] = Field(default_factory=list, description="Proposed initiatives")
    research_repository: Dict[str, Any] = Field(default_factory=dict, description="Raw empirical evidence")
    brand_profile: Dict[str, Any] = Field(default_factory=dict, description="Brand profile parameters")


class BrandProfile(BaseModel):
    """Target brand entity specifications."""

    website_url: str = Field(..., description="Target brand root URL")
    brand_name: str = Field(..., description="Client or brand trade name")
    industry: str = Field(..., description="Domain vertical / sector")
    target_market: List[str] = Field(default_factory=list, description="Primary customer segments")
    business_goals: List[str] = Field(
        default_factory=list,
        description="Explicit commercial objectives",
    )


class ResearchRepository(BaseModel):
    """Ground truth repository containing empirical audit evidence."""

    dom_snapshots: Dict[str, Any] = Field(
        default_factory=dict,
        description="Cleaned DOM trees keyed by page route",
    )
    visual_evidence_vnc: List[EvidenceReference] = Field(
        default_factory=list,
        description="Screenshots and bounding box captures",
    )
    competitor_profiles: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Discovered competitor benchmarks",
    )
    rag_citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Retrieved client document chunks",
    )
    context_gaps: List[str] = Field(
        default_factory=list,
        description="Explicitly recorded information limitations",
    )


class StrategicArtifacts(BaseModel):
    """Synthesized domain intelligence produced across pipeline stages."""

    audience_analysis: Dict[str, Any] = Field(
        default_factory=dict,
        description="ICP models, customer journey, and friction indices",
    )
    brand_positioning: Dict[str, Any] = Field(
        default_factory=dict,
        description="Category of One matrix, UVP critique, narrative pillars",
    )
    seo_and_content_plan: Dict[str, Any] = Field(
        default_factory=dict,
        description="Technical audit, keyword voids, editorial calendar",
    )
    growth_initiatives: List[StrategicInitiative] = Field(
        default_factory=list,
        description="Ranked initiatives adhering to standardized contract",
    )


class MasterEngineState(BaseModel):
    """Immutable root state container passed and updated across agent stages."""

    session_id: str = Field(..., description="Unique UUID for this audit run")
    mode: OperationalMode = Field(..., description="Operational modality")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Session initialization timestamp",
    )
    brand_profile: BrandProfile = Field(..., description="Audited brand metadata")
    research_repository: ResearchRepository = Field(
        default_factory=ResearchRepository,
        description="Empirical evidence repository",
    )
    strategic_artifacts: StrategicArtifacts = Field(
        default_factory=StrategicArtifacts,
        description="Specialist outputs",
    )
    validation_report: ValidationReport = Field(
        default_factory=ValidationReport,
        description="Adversarial validation log",
    )
    current_stage: str = Field(
        default="Initialization",
        description="Active pipeline stage name",
    )
    iteration_counter: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Global revision cycle counter",
    )
