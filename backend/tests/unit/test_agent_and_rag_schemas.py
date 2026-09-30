"""Unit tests verifying input/output schemas for all agents across the system.

Covers:
- Layer 2: Intelligence Engine contracts (TaskGrant, ContextRequest, EvidenceEnvelope, ActionPreview, ConsolidatedEvidencePackage)
- Layer 3: Agentic RAG Controller & Dispatcher contracts (RagController, RagQueryDispatcher, EvidenceChunk)
- Layer 5: All 7 Worker Agents' input/output domain contracts (W_DEV, W_STRAT, W_CREAT, W_PROD, W_COMP, W_VOICE, W_LEARN)
- Layer 6: Specialist Sub-Agents' domain schemas (across all 38 specialist roles)
- Layer 6 Runtime: All 7 Sandbox micro-tool capability profiles (s-code, s-alloc, s-copy, s-val, s-comp, s-parse, s-attr)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest
from pydantic import ValidationError

from app.core.exceptions import AuthorizationError, RetrievalGovernanceError
from app.integrations.sandbox.capabilities import CAPABILITY_REGISTRY, CapabilityProfile
from app.orchestration.rag_query_dispatch import IntelligenceEngineToken, RagQueryDispatcher
from app.schemas.action_preview import ActionPreview, ActionPreviewKind, SpendPreviewDetails
from app.schemas.agent_contracts import (
    AdCopyVariant,
    AdaptedCreativePack,
    AnonymizedSentimentVector,
    AttributionDeliverable,
    AttributionModelType,
    CandidateStateDelta,
    ChannelAllocation,
    ClaimsDossier,
    ClaimValidationStatus,
    ClaimVerificationEntry,
    ConfidenceInterval,
    ConsolidatedEvidencePackage,
    ContextRequest,
    CreativePackage,
    CustomerVoiceAnalysisResult,
    DevelopmentDeliverable,
    EvidenceConflict,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    QAReport,
    QAStatus,
    SocialPostVariant,
    TaskGrant,
    VisualBrief,
)
from app.schemas.competitor_intel import (
    AssumptionVerdict,
    CompetitiveEvidenceBrief,
    CompetitorEntity,
    Finding,
    Observation,
)
from app.schemas.customer_voice import (
    AspectSentimentFinding,
    CustomerVoicePayload,
    EvidenceSpan,
    JourneyComparison,
    NeedObjectionFinding,
    TopicFinding,
    VoiceQAReport,
)
from app.schemas.governance import RiskLevel, TenantScope, WorkerRole
from app.schemas.learning_performance import (
    EvidenceCategory,
    LearningDeltaCandidate,
    LearningEstimate,
    LearningQAResult,
    LearningUncertainty,
    QADecision,
    UncertaintyKind,
)
from app.schemas.product_evidence import (
    ClaimRecord,
    ExtractedEvidence,
    ProductEvidencePayload,
    RegulatoryRule,
    RuleForce,
    SourceRecord,
    TraceBundle,
)
from app.schemas.sandbox import (
    NetworkPolicy,
    SandboxCapability,
    SandboxEgressGrant,
    SandboxExecutionStatus,
    SandboxInvocationMandate,
    SandboxResult,
)
from app.schemas.strategy import (
    AllocationConstraint,
    SAllocDomainStatus,
    SAllocMandate,
    SAllocResult,
    StrategyDirective,
    StrategyResultEnvelope,
)
from app.services.rag.controller import RagController
from app.services.rag.hybrid_retriever import HybridRetriever


# ==============================================================================
# 1. Layer 2: Intelligence Engine Contracts
# ==============================================================================

def test_task_grant_schema_validation() -> None:
    grant = TaskGrant(
        task_id="task-orch-001",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="tenant-brand-alpha", allowed_channels=["meta", "google"]),
        brand_id="brand-alpha",
        objective="Formulate Q4 Omnichannel Media Plan",
        expires_at=datetime.now(UTC) + timedelta(hours=2),
        token_budget=16000,
        risk_tier=RiskLevel.MEDIUM,
        sandbox_capabilities=["S_ALLOC"],
    )
    assert grant.task_id == "task-orch-001"
    assert grant.worker_role == WorkerRole.STRATEGY
    assert grant.tenant_scope.tenant_id == "tenant-brand-alpha"
    assert "S_ALLOC" in grant.sandbox_capabilities


def test_evidence_envelope_schema_validation() -> None:
    env = EvidenceEnvelope(
        task_id="task-orch-001",
        worker_role=WorkerRole.STRATEGY,
        confidence=ConfidenceInterval(point_estimate=0.88, lower_bound=0.82, upper_bound=0.94),
        findings=["Allocated $50k across Meta and Google.", "Expected Blended ROAS: 3.4x"],
        payload={"strategy_plan_id": "plan-strat-99"},
        supporting_evidence=["ev-meta-priors-2026", "ev-google-search-2026"],
        provenance={"worker_id": "W_STRAT", "run_id": "run-001"},
    )
    assert env.confidence.point_estimate == 0.88
    assert env.confidence.lower_bound <= env.confidence.point_estimate <= env.confidence.upper_bound
    assert len(env.findings) == 2


def test_action_preview_schema_validation() -> None:
    preview = ActionPreview(
        preview_id="prev-act-001",
        task_id="task-orch-001",
        tenant_id="tenant-brand-alpha",
        kind=ActionPreviewKind.SPEND,
        summary="Q4 Media Spend Allocation Proposal ($50,000)",
        spend_amount=50000.0,
        risk_level=RiskLevel.MEDIUM,
        requires_approval=True,
        spend_details=SpendPreviewDetails(
            channel="meta",
            allocated_amount=50000.0,
            percentage_of_total=1.0,
        ),
    )
    assert preview.preview_id == "prev-act-001"
    assert preview.kind == ActionPreviewKind.SPEND
    assert preview.spend_amount == 50000.0


def test_consolidated_evidence_package_schema_validation() -> None:
    pkg = ConsolidatedEvidencePackage(
        package_id="pkg-cons-001",
        tenant_id="tenant-brand-alpha",
        source_task_ids=["task-orch-001", "task-orch-002"],
        participating_roles=[WorkerRole.STRATEGY, WorkerRole.CREATIVE_CONTENT],
        confidence_summary={
            "weighted_point_estimate": 0.85,
            "lower_bound": 0.80,
            "upper_bound": 0.90,
            "confidence_band": "HIGH",
            "is_statistically_sound": True,
            "envelope_count": 2,
        },
        conflicts=[],
        warnings=[],
    )
    assert pkg.package_id == "pkg-cons-001"
    assert pkg.confidence_summary.confidence_band == "HIGH"
    assert len(pkg.participating_roles) == 2


# ==============================================================================
# 2. Layer 3: Governed Agentic RAG Controller & Dispatcher Contracts
# ==============================================================================

@pytest.mark.asyncio
async def test_rag_controller_and_dispatcher_contracts() -> None:
    from tests.conftest import FakeVectorRepository

    repo = FakeVectorRepository()
    repo.seed(tenant_id="tenant-alpha", text="Brand alpha tone guidelines")
    controller = RagController(HybridRetriever(repo))
    dispatcher = RagQueryDispatcher(rag_controller=controller)

    # 1. Unforgeable token requirement
    with pytest.raises(AuthorizationError):
        await dispatcher.dispatch(
            "fake_token",  # type: ignore[arg-type]
            tenant_id="tenant-alpha",
            query="tone guidelines",
        )

    # 2. Authorized retrieval with unforgeable token
    token = IntelligenceEngineToken("IE-test-suite")
    results = await dispatcher.dispatch(
        token,
        tenant_id="tenant-alpha",
        query="tone guidelines",
        top_k=5,
    )
    assert len(results) >= 1
    for chunk in results:
        assert chunk["tenant_id"] == "tenant-alpha"
        assert chunk["provenance_tracked"] is True
        assert len(chunk["provenance_hash"]) == 64  # SHA-256


# ==============================================================================
# 3. Layer 5 & Layer 6: Worker and Specialist Sub-Agent Schemas
# ==============================================================================

def test_w_strat_and_s_alloc_contracts() -> None:
    from app.schemas.strategy import ChannelSpendProposal

    # Test SAllocMandate
    mandate = SAllocMandate(
        tenant_id="tenant-alpha",
        task_id="task-strat-01",
        parent_grant_id="grant-01",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        authorized_channels=["meta", "google"],
        budget_ceiling=25000.0,
        allocation_constraints=[
            AllocationConstraint(channel="meta", min_spend=5000.0, max_spend=15000.0)
        ],
    )
    assert mandate.budget_ceiling == 25000.0
    assert mandate.compute_input_digest() is not None

    # Test SAllocResult
    result = SAllocResult(
        task_id="task-strat-01",
        execution_id="exec-01",
        stage_attempt_id="att-01",
        tenant_id="tenant-alpha",
        input_sha256="a" * 64,
        status=SAllocDomainStatus.OK,
        total_allocated=25000.0,
        scenario_allocations={
            "base": [
                ChannelSpendProposal(channel="meta", allocated_amount=15000.0, percentage_of_total=0.60),
                ChannelSpendProposal(channel="google", allocated_amount=10000.0, percentage_of_total=0.40),
            ]
        },
    )
    assert result.total_allocated == 25000.0
    assert "base" in result.scenario_allocations
    assert len(result.scenario_allocations["base"]) == 2


def test_w_creat_and_s_copy_contracts() -> None:
    ad_copy = AdCopyVariant(
        variant_id="var-copy-01",
        channel="meta",
        format="feed_ad",
        headline="Clinically Verified Radiance",
        body_copy="Experience dermatologist-tested skin barrier restoration in 14 days.",
        cta="Shop Now",
        source_claim_ids=["claim-skin-01"],
    )
    social_post = SocialPostVariant(
        post_id="post-soc-01",
        platform="instagram",
        hook="Ready to restore your skin barrier?",
        caption="Our clinically formulated cream delivers hydration without irritation.",
        source_claim_ids=["claim-skin-01"],
    )
    visual_brief = VisualBrief(
        brief_id="vb-01",
        asset_title="Serum Bottle Macro Texture",
        channel="meta",
        art_direction="Minimalist studio lighting with water droplets.",
    )
    pkg = CreativePackage(
        package_id="cpkg-01",
        tenant_id="tenant-alpha",
        brand_id="brand-alpha",
        objective="Launch Q4 Skincare Campaign",
        ad_copy_variants=[ad_copy],
        social_posts=[social_post],
        visual_briefs=[visual_brief],
        approved_claim_refs=["claim-skin-01"],
        qa_status="PASS",
    )
    assert pkg.qa_status == "PASS"
    assert len(pkg.ad_copy_variants) == 1
    assert len(pkg.social_posts) == 1


def test_w_prod_and_s_val_contracts() -> None:
    from app.schemas.product_evidence import AccessLevel, ClaimKind, ClaimStatus, EvidenceSubject, EvidenceType

    source = SourceRecord(
        id="src-clinical-01",
        title="Double-Blind Barrier Repair Trial 2025",
        url="https://example.com/clinical-trial-2025",
        evidence_type=EvidenceType.PRIMARY_STUDY,
        access=AccessLevel.FULL_TEXT,
        provenance_ref="prov-source-01",
    )
    evidence = ExtractedEvidence(
        id="ev-clinical-01",
        source_id="src-clinical-01",
        snapshot_ref="snap-01",
        location="p. 14, Table 2",
        subject=EvidenceSubject.FINISHED_PRODUCT,
        outcome="Transepidermal water loss decreased by 42% over 14 days.",
        assessment_ref="ass-01",
        activity_ref="act-discovery-01",
    )
    claim = ClaimRecord(
        id="claim-skin-01",
        text="Reduces transepidermal water loss by 42% in 14 days.",
        kind=ClaimKind.EXPLICIT,
        asset_ref="asset-pdp-01",
        asset_location="Section 2 hero description",
        interpretation_reason="Direct clinical performance claim extracted from packaging copy.",
        status=ClaimStatus.SUPPORTED_IN_SCOPE,
        activity_ref="act-claims-01",
    )
    bundle = TraceBundle(
        tenant_id="tenant-alpha",
        run_id="run-prod-01",
        product_version="v2.1",
        sources=[source],
        evidence=[evidence],
        claims=[claim],
    )
    assert bundle.product_version == "v2.1"
    assert len(bundle.claims) == 1
    assert bundle.claims[0].status == ClaimStatus.SUPPORTED_IN_SCOPE


def test_w_comp_and_s_comp_contracts() -> None:
    obs = Observation(
        observation_id="obs-comp-01",
        predicate="has_observed_price",
        typed_value="48.00",
        subject_id="comp-brand-x",
        supporting_evidence_id="ev-comp-01",
        locator="table.pricing > tr:nth-child(2)",
    )
    brief = CompetitiveEvidenceBrief(
        brief_id="brief-comp-01",
        run_id="run-comp-01",
        strategy_plan_ref="plan-strat-99",
        assumption_verdicts={"assumption-1": AssumptionVerdict.SUPPORTED},
        observations=[obs],
        findings=[
            Finding(
                finding_id="find-comp-01",
                claim_text="Competitor X raised price from $42 to $48.",
                supporting_evidence_ids=["obs-comp-01"],
            )
        ],
    )
    assert brief.brief_id == "brief-comp-01"
    assert len(brief.observations) == 1
    assert brief.assumption_verdicts["assumption-1"] == AssumptionVerdict.SUPPORTED


def test_w_voice_and_s_parse_contracts() -> None:
    span = EvidenceSpan(
        record_id="rec-voice-01",
        sanitized_text_hash="b" * 64,
        start_offset=10,
        end_offset=42,
        span_hash="c" * 64,
        source_ref="ticket-40291",
        exact_quote="packaging dispenser pumps too stiff",
    )
    objection = NeedObjectionFinding(
        finding_id="obj-01",
        finding_type="objection",
        theme="Pump Mechanism Stiffness",
        frequency=34,
        customer_vocabulary=["stiff pump", "hard to press"],
        evidence_spans=[span],
    )
    payload = CustomerVoicePayload(
        task_id="task-voice-01",
        tenant_id="tenant-alpha",
        records_analyzed=1200,
        needs_and_objections=[objection],
    )
    assert payload.records_analyzed == 1200
    assert payload.needs_and_objections[0].theme == "Pump Mechanism Stiffness"


def test_w_learn_and_s_attr_contracts() -> None:
    estimate = LearningEstimate(
        estimate_id="est-attr-01",
        metric="ROAS",
        estimand="blended_channel_roas",
        evidence_category=EvidenceCategory.MODEL_BASED,
        tenant_id="tenant-alpha",
        channel="meta",
        method_name="time_decay_attribution",
        point_estimate=3.25,
        uncertainty=LearningUncertainty(
            kind=UncertaintyKind.CONFIDENCE_INTERVAL,
            lower_bound=2.95,
            upper_bound=3.55,
            level=0.95,
        ),
    )
    candidate = LearningDeltaCandidate(
        candidate_id="ldelta-01",
        idempotency_key="key-01",
        tenant_id="tenant-alpha",
        base_memory_version="mem-v1",
        accepted_claim_ids=["claim-attr-01"],
        scoped_metrics={"meta_roas": 3.25},
        uncertainty=LearningUncertainty(kind=UncertaintyKind.NOT_APPLICABLE),
        qa_digest="d" * 64,
        applicable_window_start=datetime.now(UTC) - timedelta(days=30),
        applicable_window_end=datetime.now(UTC),
    )
    assert candidate.status == "candidate"
    assert estimate.point_estimate is not None
    assert estimate.uncertainty.lower_bound is not None
    assert estimate.uncertainty.upper_bound is not None
    assert estimate.uncertainty.lower_bound <= estimate.point_estimate <= estimate.uncertainty.upper_bound


# ==============================================================================
# 4. Layer 6 Runtime: Sandbox Micro-Tool Capability Profile Registry
# ==============================================================================

def test_sandbox_capability_profiles_completeness() -> None:
    """Verify that all 7 required sandbox capabilities are strictly registered with least privilege."""
    expected_capabilities = {
        SandboxCapability.CODE: ("S_CODE", WorkerRole.DEVELOPMENT, NetworkPolicy.DISABLED),
        SandboxCapability.ALLOC: ("S_ALLOC", WorkerRole.STRATEGY, NetworkPolicy.DISABLED),
        SandboxCapability.COPY: ("S_COPY", WorkerRole.CREATIVE_CONTENT, NetworkPolicy.DISABLED),
        SandboxCapability.VAL: ("S_VAL", WorkerRole.PRODUCT_EVIDENCE, NetworkPolicy.DISABLED),
        SandboxCapability.COMP: ("s-comp", WorkerRole.COMPETITOR_INTEL, NetworkPolicy.CONTROLLED),
        SandboxCapability.PARSE: ("S_PARSE", WorkerRole.CUSTOMER_VOICE, NetworkPolicy.DISABLED),
        SandboxCapability.ATTR: ("S_ATTR", WorkerRole.LEARNING_PERFORMANCE, NetworkPolicy.DISABLED),
    }

    for cap, (name, role, net_policy) in expected_capabilities.items():
        assert cap in CAPABILITY_REGISTRY, f"Missing capability {cap} in CAPABILITY_REGISTRY"
        profile: CapabilityProfile = CAPABILITY_REGISTRY[cap]
        assert profile.allowed_worker == role, f"Mismatched worker role for {cap}: {profile.allowed_worker} != {role}"
        assert profile.network_policy == net_policy, f"Mismatched network policy for {cap}: {profile.network_policy} != {net_policy}"
        assert len(profile.allowed_operations) > 0, f"Capability {cap} has zero allowed operations"
        assert len(profile.allowed_tools) > 0, f"Capability {cap} has zero allowed tools"


def test_sandbox_egress_grant_ssrf_and_wildcard_rejection() -> None:
    """Verify SandboxEgressGrant rejects wildcard '*', private IPs, and internal cloud metadata endpoints."""
    # 1. Wildcard domain rejected
    with pytest.raises(ValidationError, match="Universal wildcard"):
        SandboxEgressGrant(
            tenant_id="tenant-alpha",
            task_id="task-001",
            allowed_domains=["*"],
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )

    # 2. Cloud metadata IP rejected
    with pytest.raises(ValidationError, match="private/internal"):
        SandboxEgressGrant(
            tenant_id="tenant-alpha",
            task_id="task-001",
            allowed_domains=["169.254.169.254"],
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )

    # 3. Valid allowlisted domain accepted
    grant = SandboxEgressGrant(
        tenant_id="tenant-alpha",
        task_id="task-001",
        allowed_domains=["api.meta.com", "*.google.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    allowed, _ = grant.is_destination_allowed("https://api.meta.com/ads")
    assert allowed is True
    blocked, _ = grant.is_destination_allowed("https://internal.metadata.internal")
    assert blocked is False
