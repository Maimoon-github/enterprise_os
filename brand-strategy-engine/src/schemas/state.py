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


class BuyerPersona(BaseModel):
    """Grounded buyer persona model."""

    name: str = Field(..., description="Persona title or professional role")
    role_archetype: str = Field(..., description="Role archetype e.g. Engineering Director, eCommerce Shopper")
    intent_classification: str = Field(..., description="Intent classification (e.g. High-Consideration B2B, Impulse eCommerce)")
    core_needs: List[str] = Field(default_factory=list, description="Key decision criteria and priorities")
    friction_triggers: List[str] = Field(default_factory=list, description="Friction triggers and bounce factors")
    grounded_evidence_ids: List[str] = Field(default_factory=list, description="Empirical evidence_id or RAG chunk_id references")


class JourneyTouchpoint(BaseModel):
    """Customer journey touchpoint and friction assessment."""

    stage: str = Field(..., description="Journey stage (e.g. Discovery, Evaluation, Conversion)")
    touchpoint_name: str = Field(..., description="Name of touchpoint (e.g. Hero Discovery, PDP Accordion, Checkout)")
    friction_score: float = Field(..., ge=1.0, le=10.0, description="Quantified friction rating from 1.0 to 10.0")
    drop_off_trigger: str = Field(..., description="Key cause of visitor drop-off")
    grounded_evidence_id: Optional[str] = Field(default=None, description="Linked evidence_id or chunk_id citation")


class AudienceAnalysis(BaseModel):
    """Strongly typed audience strategy artifact."""

    icp_profile: Dict[str, Any] = Field(..., description="Structured ICP profile")
    buyer_personas: List[BuyerPersona] = Field(default_factory=list, description="Grounded buyer personas")
    intent_classification: str = Field(..., description="Primary visitor intent classification")
    journey_touchpoints: List[JourneyTouchpoint] = Field(default_factory=list, description="Mapped customer journey stages")
    friction_index: float = Field(..., ge=1.0, le=10.0, description="Overall quantified funnel friction index")
    journey_breakdown: Dict[str, str] = Field(default_factory=dict, description="Stage-by-stage friction breakdown")
    persona_alignment_ratings: Dict[str, float] = Field(default_factory=dict, description="Persona-to-content alignment ratings (1.0 to 10.0)")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class AudienceSlice(BaseModel):
    """Bounded state slice injected into Agent 2 (Audience Strategist)."""

    mode: str = Field(..., description="Operational modality")
    industry: str = Field(..., description="Industry vertical")
    target_market: List[str] = Field(default_factory=list, description="Target customer segments")
    observation_notes: str = Field(default="", description="Visual and touchpoint observation notes")
    business_goals: List[str] = Field(default_factory=list, description="Commercial goals")
    competitors: List[Dict[str, Any]] = Field(default_factory=list, description="Competitor profiles")
    visual_evidence_ids: List[str] = Field(default_factory=list, description="Visual evidence IDs from Agent 1")
    dom_summary: Dict[str, Any] = Field(default_factory=dict, description="Pruned DOM summaries from Agent 1")
    rag_citations: List[Dict[str, Any]] = Field(default_factory=list, description="Retrieved client RAG chunks")


class BrandPositioning(BaseModel):
    """Strongly typed brand positioning artifact."""

    category_of_one: str = Field(..., description="Defensible Category of One positioning statement")
    core_messaging_hierarchy: Dict[str, Any] = Field(
        default_factory=dict,
        description="Core messaging hierarchy: primary headline, subheadings, value propositions, and proof points",
    )
    differentiation_matrix: Dict[str, Any] = Field(
        default_factory=dict,
        description="Category of One differentiation matrix vs competitor vectors",
    )
    uvp_evaluation: str = Field(
        default="",
        description="High-level UVP rating (e.g. Commoditized vs Differentiated)",
    )
    uvp_critique: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed UVP clarity evaluation, deficiency diagnosis, and recommended focus",
    )
    commoditized_claim_flags: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Cross-checked competitor overlapping claims flagged as commoditized",
    )
    identity_improvement_playbook: List[str] = Field(
        default_factory=list,
        description="Actionable playbook for tonal, narrative, and authority improvements",
    )
    narrative_pillars: List[str] = Field(
        default_factory=list,
        description="Empirical narrative pillars",
    )
    evidence_citations: List[str] = Field(
        default_factory=list,
        description="Linked empirical evidence_id or RAG chunk_id citations",
    )

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class BrandSlice(BaseModel):
    """Bounded state slice injected into Agent 3 (Brand Strategist)."""

    mode: str = Field(..., description="Operational modality")
    headline: str = Field(default="", description="Extracted hero headline copy")
    brand_name: str = Field(..., description="Target brand name")
    audience_icp: Dict[str, Any] = Field(default_factory=dict, description="ICP model from Agent 2")
    competitors: List[Dict[str, Any]] = Field(default_factory=list, description="Competitor profiles")
    visual_summaries: List[str] = Field(
        default_factory=list,
        description="Analyst visual summaries and observation notes",
    )
    visual_evidence_ids: List[str] = Field(
        default_factory=list,
        description="Visual evidence IDs from Agent 1",
    )
    subheadings: List[str] = Field(
        default_factory=list,
        description="Extracted subheading copy snippets",
    )
    competitor_messaging: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Competitor messaging vectors from research repository",
    )
    audience_analysis: Dict[str, Any] = Field(
        default_factory=dict,
        description="Full audience strategy analysis from Agent 2",
    )
    rag_citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Retrieved client document chunks",
    )

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class TechnicalSEOIssue(BaseModel):
    """Grounded technical SEO issue bound to an exact DOM selector and empirical evidence_id."""

    issue_id: str = Field(..., description="Unique issue identifier")
    category: str = Field(..., description="Technical category (e.g. Schema Markup, Canonicalization, Headings, Meta)")
    severity: str = Field(..., description="Severity rating (Critical, Warning, Optimization)")
    dom_selector: str = Field(..., description="Exact DOM node selector citing the flaw")
    evidence_id: str = Field(..., description="Empirical evidence citation (ev_dom_... or chk_...)")
    description: str = Field(..., description="Detailed diagnostic description")
    actionable_fix: str = Field(..., description="Prescribed remediation steps")
    cms_feasibility: str = Field(..., description="CMS-scoped implementation constraint (WordPress, Shopify, Webflow, Next.js)")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class KeywordOpportunity(BaseModel):
    """Keyword opportunity strictly mapped to search intent to prevent keyword stuffing."""

    keyword: str = Field(..., description="Target search query or cluster")
    search_intent: str = Field(..., description="Explicit search intent: Informational, Commercial, or Transactional")
    target_page: str = Field(default="", description="Recommended landing page or URL path")
    difficulty: str = Field(default="Medium", description="Competitive ranking difficulty")
    estimated_relevance: float = Field(default=8.0, ge=1.0, le=10.0, description="Relevance to brand positioning (1-10)")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class ContentGap(BaseModel):
    """Semantic content void identified against competitor coverage."""

    topic: str = Field(..., description="Unaddressed high-value topic or case study theme")
    competitor_coverage: str = Field(..., description="Observed competitor coverage summary")
    intent: str = Field(..., description="Target visitor intent (Informational, Commercial, Transactional)")
    recommended_format: str = Field(default="Technical Case Study", description="Editorial format")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class SEOAndContentPlan(BaseModel):
    """Strongly typed strategic SEO and content artifact produced by Agent 4."""

    technical_health: Dict[str, Any] = Field(
        default_factory=dict,
        description="High-level technical audit summary (schema_org, title_tag, canonical_tag, cms_feasibility)",
    )
    technical_issue_log: List[TechnicalSEOIssue] = Field(
        default_factory=list,
        description="Grounded technical SEO flaws bound to DOM nodes and evidence IDs",
    )
    content_gap_inventory: List[ContentGap] = Field(
        default_factory=list,
        description="Identified content voids against competitors",
    )
    keyword_opportunity_matrix: List[KeywordOpportunity] = Field(
        default_factory=list,
        description="Ranked keywords strictly categorized by intent",
    )
    content_editorial_blueprint: List[str] = Field(
        default_factory=list,
        description="Strategic content calendar and editorial roadmap",
    )
    high_intent_keywords: List[str] = Field(
        default_factory=list,
        description="High-intent commercial and transactional keywords for backward compatibility",
    )
    cms_platform: str = Field(
        default="Standard CMS (WordPress/Shopify/Webflow/Next.js)",
        description="Identified or scoped CMS framework",
    )
    evidence_citations: List[str] = Field(
        default_factory=list,
        description="Empirical evidence_id or RAG chunk_id citations",
    )

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class SEOSlice(BaseModel):
    """Bounded state slice injected into Agent 4 (SEO & Content Strategist)."""

    mode: str = Field(..., description="Operational modality")
    website_url: str = Field(..., description="Target website URL")
    dom_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Captured DOM metadata and hierarchy")
    dom_snapshots: Dict[str, Any] = Field(default_factory=dict, description="Captured DOM trees keyed by page route")
    competitor_profiles: List[Dict[str, Any]] = Field(default_factory=list, description="Discovered competitor benchmarks")
    brand_positioning: Dict[str, Any] = Field(default_factory=dict, description="Synthesized brand positioning")
    rag_citations: List[Dict[str, Any]] = Field(default_factory=list, description="Retrieved client document chunks")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class GrowthSlice(BaseModel):
    """Bounded state slice injected into Agent 5 (Growth Strategist)."""

    mode: str = Field(..., description="Operational modality")
    website_url: str = Field(..., description="Target website URL")
    brand_profile: Dict[str, Any] = Field(default_factory=dict, description="Target brand specifications")
    audience_analysis: Dict[str, Any] = Field(default_factory=dict, description="Audience analysis")
    brand_positioning: Dict[str, Any] = Field(default_factory=dict, description="Brand positioning")
    seo_and_content_plan: Dict[str, Any] = Field(default_factory=dict, description="SEO and content blueprint")
    visual_evidence_vnc: List[EvidenceReference] = Field(default_factory=list, description="Empirical visual evidence")
    research_repository: Dict[str, Any] = Field(default_factory=dict, description="Indexed evidence records")
    rag_citations: List[Dict[str, Any]] = Field(default_factory=list, description="Retrieved client document chunks")
    business_goals: List[str] = Field(default_factory=list, description="Commercial goals")
    rejection_reasons: Optional[List[str]] = Field(default=None, description="Validator feedback for revision cycle")
    iteration_cycle: int = Field(default=0, ge=0, le=3, description="Current revision iteration cycle")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


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
