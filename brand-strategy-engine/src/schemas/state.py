"""Unified state contracts for Universal AI Brand Strategy Engine."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List
from pydantic import BaseModel, Field

from src.schemas.evidence import EvidenceReference
from src.schemas.initiative import StrategicInitiative
from src.schemas.validation import ValidationReport


class OperationalMode(str, Enum):
    """Operational modality for the engine."""

    MODE_A_PERSONAL = "Mode_A_Personal"
    MODE_B_ECOMMERCE = "Mode_B_eCommerce"


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
        default_factory=datetime.utcnow,
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
