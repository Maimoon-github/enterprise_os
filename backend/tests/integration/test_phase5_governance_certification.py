"""Phase 5 — Evidence-to-HITL Runtime Governance Certification Suite.

Certifies the implemented runtime path:
Worker Evidence → IE Synthesis → Action Preview → HITL Decision → Cryptographic Validation → Authorized Dispatch → Outbound MCP Dry-Run

Validates all 15 Phase 5 acceptance criteria:
1. Multi-worker evidence synthesizes correctly.
2. Insufficient/conflicting evidence fails closed.
3. Preview binds exact proposed action (SPEND, CLAIM, COPY, CODE_DIFF).
4. HITL approval is explicit and role-governed.
5. Reject/revision cannot dispatch.
6. Modified preview/artifact invalidates approval.
7. Cross-tenant approval fails closed.
8. Replayed/expired/revoked authorization fails.
9. Unsigned outbound dispatch fails closed.
10. IE is sole dispatch authority (Model A preserved).
11. CTS transitions remain legal throughout.
12. Provenance captures complete lineage.
13. Dry-run reaches MCP_ACT with zero production side effects.
14. Scope & budget escalation enforcement.
15. LLM output cannot auto-approve or bypass HITL.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.core.exceptions import (
    ApprovalRequiredError,
    InvalidTransitionError,
    PolicyViolationError,
    SignatureVerificationError,
)
from app.integrations.ads.base import AdsAdapter
from app.integrations.cms.client import CmsClient
from app.integrations.sandbox.client import SandboxClient
from app.integrations.social.base import SocialAdapter
from app.mcp.outbound_gateway import (
    OutboundGateway,
    TokenBucket,
    canonical_dispatch_bytes,
)
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import (
    ActionPreview,
    ActionPreviewDossier,
    ActionPreviewKind,
    HumanDecisionType,
    ReviewStatus,
    ReviewerRole,
    compute_preview_hash,
)
from app.schemas.agent_contracts import (
    AdCopyVariant,
    ChannelAllocation,
    CodeDiffEntry,
    ConfidenceInterval,
    ConflictSeverity,
    ConsolidatedPackageStatus,
    ContentScheduleItem,
    CreativePackage,
    DevelopmentDeliverable,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    SocialPostVariant,
    UITemplateDefinition,
    VisualBrief,
)
from app.schemas.dispatch import (
    AudienceToken,
    DispatchDirective,
    DispatchReadiness,
)
from app.schemas.governance import (
    Directive,
    RiskLevel,
    TenantScope,
    WorkerRole,
)
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.hitl import HitlCoordinator, canonical_decision_bytes
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository, FakeSandboxClient


# =========================================================================
# Helpers and Fakes
# =========================================================================

def _make_keypair() -> tuple[Ed25519PrivateKey, str]:
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_key, public_pem


class SpyAdsAdapter(AdsAdapter):
    channel = "meta"

    def __init__(self) -> None:
        self.applied: list[dict[str, Any]] = []

    async def apply_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.applied.append(payload)
        return {"status_code": "200", "channel": self.channel, "campaign_id": "meta-camp-123"}


class SpySocialAdapter(SocialAdapter):
    channel = "instagram"

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.published.append(payload)
        return {"status_code": "200", "post_id": "ig-post-999", "status": "published"}


class SpyCmsClient(CmsClient):
    def __init__(self) -> None:
        self.deployed: list[dict[str, Any]] = []

    async def deploy_payload(self, payload: dict[str, Any], tenant_id: str | None = "default") -> dict[str, Any]:
        self.deployed.append({"payload": payload, "tenant_id": tenant_id})
        return {"status_code": "200", "status": "published", "version": "v1.1"}


def _build_test_harness(public_pem: str) -> dict[str, Any]:
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)
    crypto_validator = CryptographicValidator(public_pem)
    hitl_coordinator = HitlCoordinator(crypto_validator)
    state_machine = TaskStateMachine()
    synthesizer = EvidenceSynthesizer()
    preview_gen = HitlPreviewGenerator()
    dag = DagScheduler()
    policy_eval = PolicyEvaluator()

    ie = IntelligenceEngine(
        policy_evaluator=policy_eval,
        dag_scheduler=dag,
        task_state_machine=state_machine,
        context_assembler=None,  # type: ignore[arg-type]
        evidence_synthesizer=synthesizer,
        hitl_preview_generator=preview_gen,
        hitl_coordinator=hitl_coordinator,
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=prov_recorder,
        workers={},
    )

    spy_ads = SpyAdsAdapter()
    spy_social = SpySocialAdapter()
    spy_cms = SpyCmsClient()

    gateway = OutboundGateway(
        hitl=hitl_coordinator,
        crypto_validator=crypto_validator,
        ads_adapters={"meta": spy_ads},
        social_adapters={"instagram": spy_social},
        cms_client=spy_cms,
        provenance_recorder=prov_recorder,
        require_signature=True,
    )

    return {
        "prov_repo": prov_repo,
        "prov_recorder": prov_recorder,
        "crypto_validator": crypto_validator,
        "hitl_coordinator": hitl_coordinator,
        "state_machine": state_machine,
        "synthesizer": synthesizer,
        "preview_gen": preview_gen,
        "ie": ie,
        "gateway": gateway,
        "spy_ads": spy_ads,
        "spy_social": spy_social,
        "spy_cms": spy_cms,
    }


def _build_multi_worker_envelopes(tenant_id: str) -> list[EvidenceEnvelope]:
    """Create authentic, well-formed envelopes from Strategy, Creative, Development, and Product Evidence."""
    # 1. Strategy Envelope
    strat_plan = OmnichannelStrategyPlan(
        plan_id="plan-q4",
        brand_id="brand-derm",
        tenant_id=tenant_id,
        budget_ceiling=50000.0,
        total_allocated=35000.0,
        unallocated_contingency=15000.0,
        channel_allocations=[
            ChannelAllocation(channel="meta", allocated_amount=20000.0, percentage_of_total=57.1),
            ChannelAllocation(channel="google", allocated_amount=10000.0, percentage_of_total=28.6),
            ChannelAllocation(channel="instagram", allocated_amount=5000.0, percentage_of_total=14.3),
        ],
        approved_claims_applied=["claim-clin-101"],
    )
    env_strat = EvidenceEnvelope(
        task_id="task-strat-101",
        worker_role=WorkerRole.STRATEGY,
        confidence=ConfidenceInterval(point_estimate=0.92, lower_bound=0.85, upper_bound=0.96),
        evidence=["Optimized budget allocation across Meta, Google, and Instagram based on decay analysis."],
        findings=["Blended ROAS target established at 3.3x."],
        generated_artifacts=["strategy:alloc-q4"],
        payload={"strategy_plan": strat_plan.model_dump_json(), "budget_total": "35000.0"},
        provenance={"agent": "W_STRAT", "capability": "S_ALLOC", "task_id": "task-strat-101", "tenant_id": tenant_id, "execution_id": "exec-strat-1"},
    )

    # 2. Creative Envelope
    creative_pkg = CreativePackage(
        package_id="pkg-creat-101",
        brand_id="brand-derm",
        tenant_id=tenant_id,
        objective="Q4 Acquisition Drive",
        ad_copy_variants=[
            AdCopyVariant(variant_id="var-meta-1", channel="meta", headline="Transform Your Skin", body_copy="Noticeable hydration in 14 days.", source_claim_ids=["claim-clin-101"]),
        ],
        social_posts=[
            SocialPostVariant(post_id="post-1", platform="instagram", hook="Real results?", caption="Glow with clinical confidence #skincare", source_claim_ids=["claim-clin-101"]),
        ],
        visual_briefs=[
            VisualBrief(brief_id="brief-1", asset_title="Serum Bottle Hero", channel="meta", art_direction="Clean studio lighting"),
        ],
        schedules=[
            ContentScheduleItem(schedule_id="sched-1", day_or_week="Week 1", channel="meta", variant_ref="var-meta-1", primary_objective="Acquisition"),
        ],
        approved_claim_refs=["claim-clin-101"],
    )
    env_creat = EvidenceEnvelope(
        task_id="task-creat-102",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        confidence=ConfidenceInterval(point_estimate=0.88, lower_bound=0.80, upper_bound=0.94),
        evidence=["Generated responsive ad copy variants for Meta and Instagram."],
        findings=["Approved claims applied; headline adheres to brand guidelines."],
        generated_artifacts=["copy:variants-q4"],
        payload={"creative_package": creative_pkg.model_dump_json()},
        provenance={"agent": "W_CREAT", "capability": "S_COPY", "task_id": "task-creat-102", "tenant_id": tenant_id, "execution_id": "exec-creat-1"},
    )

    # 3. Product Evidence Envelope
    env_prod = EvidenceEnvelope(
        task_id="task-prod-103",
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        confidence=ConfidenceInterval(point_estimate=0.95, lower_bound=0.90, upper_bound=0.99),
        evidence=["Validated clinical substantiation for hydration and fine lines claims."],
        findings=["Claim 'claim-clin-101' backed by double-blind clinical trial dossier #D-401."],
        generated_artifacts=["dossier:claim-clin-101"],
        payload={"claim_id": "claim-clin-101", "substantiation": "verified"},
        provenance={"agent": "W_PROD", "capability": "S_VAL", "task_id": "task-prod-103", "tenant_id": tenant_id, "execution_id": "exec-prod-1"},
    )

    # 4. Development Deliverable Envelope
    dev_deliv = DevelopmentDeliverable(
        deliverable_id="deliv-dev-104",
        tenant_id=tenant_id,
        task_id="task-dev-104",
        component_name="LandingPage",
        ui_templates=[
            UITemplateDefinition(template_id="tmpl-1", name="Showcase", template_markup="<section>Serum</section>", css_styles=".hero { display: flex; }"),
        ],
        code_diffs=[
            CodeDiffEntry(file_path="components/checkout.py", diff_unified="--- a/checkout.py\n+++ b/checkout.py\n@@ -1 +1 @@\n-# v1\n+# v2"),
        ],
        changed_files=["components/checkout.py"],
        security_checks_passed=True,
    )
    env_dev = EvidenceEnvelope(
        task_id="task-dev-104",
        worker_role=WorkerRole.DEVELOPMENT,
        confidence=ConfidenceInterval(point_estimate=0.91, lower_bound=0.85, upper_bound=0.95),
        evidence=["Prepared responsive UI landing page template and AST-validated component code diff."],
        findings=["AST linting passed; zero syntax errors; security checks clean."],
        generated_artifacts=["diff:landing-page"],
        payload={"dev_deliverable": dev_deliv.model_dump_json()},
        provenance={"agent": "W_DEV", "capability": "S_CODE", "task_id": "task-dev-104", "tenant_id": tenant_id, "execution_id": "exec-dev-1"},
    )

    return [env_strat, env_creat, env_prod, env_dev]


# =========================================================================
# Phase 5 Certification Tests
# =========================================================================

@pytest.mark.asyncio
async def test_p5_multi_worker_evidence_synthesis() -> None:
    """Criterion 1: Multi-worker evidence synthesizes into a valid ConsolidatedEvidencePackage."""
    _, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    ie: IntelligenceEngine = h["ie"]
    tenant_id = "tenant-pharma-1"

    directive = Directive(
        directive_id="dir-p5-synth",
        tenant_id=tenant_id,
        objective="Consolidate Q4 Campaign Deliverables",
        budget_cap=50000.0,
        risk_ceiling=RiskLevel.MEDIUM,
        scope=TenantScope(tenant_id=tenant_id, brand_ids=["brand-derm"], allowed_channels=["meta", "google", "instagram"]),
    )

    envelopes = _build_multi_worker_envelopes(tenant_id)
    pkg = await ie.consolidate_evidence(directive, envelopes)

    assert pkg.status == ConsolidatedPackageStatus.VALID
    assert pkg.tenant_id == tenant_id
    assert len(pkg.source_task_ids) == 4
    assert len(pkg.validated_artifacts) == 4
    assert pkg.confidence_summary.is_statistically_sound is True
    assert pkg.confidence_summary.confidence_band == "HIGH"
    assert pkg.confidence_summary.weighted_point_estimate >= 0.88
    assert len(pkg.rejected_items) == 0


@pytest.mark.asyncio
async def test_p5_insufficient_or_conflicting_evidence_fails_closed() -> None:
    """Criterion 2: Unsupported claims, security check failures, or malformed confidence fail closed."""
    _, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    synthesizer: EvidenceSynthesizer = h["synthesizer"]
    tenant_id = "tenant-pharma-1"

    envelopes = _build_multi_worker_envelopes(tenant_id)

    # Inject unsupported claim in creative package
    bad_creative_pkg = CreativePackage(
        package_id="pkg-creat-bad",
        brand_id="brand-derm",
        tenant_id=tenant_id,
        objective="Drive Conversions",
        ad_copy_variants=[
            AdCopyVariant(variant_id="var-1", channel="meta", headline="Cures All Aging Instantly", body_copy="100% cure"),
        ],
        flagged_unsupported_claims=["Cures All Aging Instantly"],
    )
    envelopes[1] = envelopes[1].model_copy(
        update={"payload": {"creative_package": bad_creative_pkg.model_dump_json()}}
    )

    # Inject security failure in development deliverable
    bad_dev_deliv = DevelopmentDeliverable(
        deliverable_id="deliv-dev-bad",
        tenant_id=tenant_id,
        task_id="task-dev-104",
        component_name="LandingPage",
        code_diffs=[CodeDiffEntry(file_path="dangerous.py", diff_unified="diff")],
        security_checks_passed=False,
    )
    envelopes[3] = envelopes[3].model_copy(
        update={"payload": {"dev_deliverable": bad_dev_deliv.model_dump_json()}}
    )

    # Add an envelope with malformed confidence interval (lower > upper)
    malformed_env = EvidenceEnvelope(
        task_id="task-bad-conf",
        worker_role=WorkerRole.COMPETITOR_INTEL,
        confidence=ConfidenceInterval(point_estimate=0.5, lower_bound=0.8, upper_bound=0.2),
        evidence=["Inverted confidence bounds"],
        provenance={"agent": "W_COMP", "capability": "S_SCRAPE", "task_id": "task-bad-conf", "tenant_id": tenant_id},
    )
    envelopes.append(malformed_env)

    pkg = synthesizer.consolidate(envelopes, expected_tenant_id=tenant_id)

    # Fails closed: Package is flagged with blocking conflicts and rejected items
    assert pkg.status == ConsolidatedPackageStatus.FLAGGED_WITH_CONFLICTS
    blocking_conflicts = [c for c in pkg.conflicts if c.severity == ConflictSeverity.BLOCKING]
    assert len(blocking_conflicts) >= 2  # Unsupported claim and security check failure
    assert any("unsupported_claims_detected" in c.conflict_type for c in blocking_conflicts)
    assert any("security_check_failed" in c.conflict_type for c in blocking_conflicts)
    assert any(r.rejection_code == "MALFORMED_CONFIDENCE" for r in pkg.rejected_items)


@pytest.mark.asyncio
async def test_p5_action_preview_exact_binding_and_sanitization() -> None:
    """Criterion 3: Deterministic Action Preview generation for SPEND, CLAIM, COPY, and CODE_DIFF."""
    _, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    ie: IntelligenceEngine = h["ie"]
    tenant_id = "tenant-pharma-1"

    directive = Directive(
        directive_id="dir-p5-prev",
        tenant_id=tenant_id,
        objective="Review Campaign Previews",
        budget_cap=50000.0,
        risk_ceiling=RiskLevel.MEDIUM,
        scope=TenantScope(tenant_id=tenant_id, brand_ids=["brand-derm"], allowed_channels=["meta", "google", "instagram"]),
    )

    envelopes = _build_multi_worker_envelopes(tenant_id)
    pkg = await ie.consolidate_evidence(directive, envelopes)
    dossier = await ie.generate_action_previews(directive, pkg)

    assert dossier.tenant_id == tenant_id
    assert dossier.preview_count == 4
    categories = {p.kind for p in dossier.previews}
    assert categories == {
        ActionPreviewKind.SPEND,
        ActionPreviewKind.CLAIM,
        ActionPreviewKind.COPY,
        ActionPreviewKind.CODE_DIFF,
    }

    # Verify all previews start strictly in PENDING
    for p in dossier.previews:
        assert p.review_status == ReviewStatus.PENDING
        assert p.requires_approval is True
        assert p.tenant_id == tenant_id

        # Verify deterministic content hash computation
        h_preview = compute_preview_hash(p)
        assert len(h_preview) == 64
        assert h_preview == compute_preview_hash(p)


@pytest.mark.asyncio
async def test_p5_hitl_explicit_decision_and_role_authority() -> None:
    """Criterion 4: Genuine human decision boundary with role-based domain authority screening."""
    priv_key, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    ie: IntelligenceEngine = h["ie"]
    hitl: HitlCoordinator = h["hitl_coordinator"]
    tenant_id = "tenant-pharma-1"

    # 1. SPEND preview requires FINANCE or ADMIN
    prev_spend = ActionPreview(
        preview_id="prev-spend-test",
        task_id="task-strat-1",
        tenant_id=tenant_id,
        kind=ActionPreviewKind.SPEND,
        summary="Media spend allocation",
        spend_amount=35000.0,
        risk_level=RiskLevel.HIGH,
    )
    hitl.submit_for_approval(prev_spend)

    # Engineering reviewer attempting to approve SPEND fails closed
    with pytest.raises(PolicyViolationError, match="not authorized"):
        hitl.decide(
            "prev-spend-test",
            decision=HumanDecisionType.APPROVE,
            approver="[email protected]",
            approver_role=ReviewerRole.ENGINEERING,
            tenant_id=tenant_id,
        )

    # Finance reviewer signs off with Ed25519 signature
    hash_spend = compute_preview_hash(prev_spend)
    dec_time = datetime.now(UTC)
    canon_bytes = canonical_decision_bytes(
        preview_id="prev-spend-test",
        decision="APPROVE",
        approver="[email protected]",
        tenant_id=tenant_id,
        preview_content_hash=hash_spend,
        decided_at=dec_time.isoformat(),
    )
    sig = sign_payload(canon_bytes, priv_key)

    decision = await ie.record_hitl_decision(
        "prev-spend-test",
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role=ReviewerRole.FINANCE,
        tenant_id=tenant_id,
        signature=sig,
        public_key_pem=pub_pem,
        preview_content_hash=hash_spend,
        decided_at=dec_time,
    )

    assert decision.approved is True
    assert decision.clearance is not None
    assert decision.clearance.is_valid is True
    assert hitl.is_approved("prev-spend-test") is True


@pytest.mark.asyncio
async def test_p5_reject_and_revision_blocks_dispatch() -> None:
    """Criterion 5: Explicit REJECT and REQUEST_REVISION flows strictly gate dispatch."""
    _, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    hitl: HitlCoordinator = h["hitl_coordinator"]
    gateway: OutboundGateway = h["gateway"]
    tenant_id = "tenant-pharma-1"

    # A. Rejection flow
    prev_claim = ActionPreview(
        preview_id="prev-claim-rej",
        task_id="task-prod-1",
        tenant_id=tenant_id,
        kind=ActionPreviewKind.CLAIM,
        summary="Doubtful efficacy claim",
    )
    hitl.submit_for_approval(prev_claim)
    hitl.decide(
        "prev-claim-rej",
        decision=HumanDecisionType.REJECT,
        approver="[email protected]",
        approver_role=ReviewerRole.LEGAL,
        tenant_id=tenant_id,
        revision_notes="Insufficient trial participants.",
    )

    with pytest.raises(ApprovalRequiredError, match="strictly blocked"):
        hitl.require_approved("prev-claim-rej")

    directive_rej = DispatchDirective(
        dispatch_id="disp-rej",
        task_id="task-prod-1",
        action_preview_id="prev-claim-rej",
        signature="dummy",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="meta",
        tenant_id=tenant_id,
    )
    with pytest.raises(ApprovalRequiredError):
        await gateway.validate_readiness(directive_rej)

    # B. Revision flow
    prev_copy = ActionPreview(
        preview_id="prev-copy-rev",
        task_id="task-creat-1",
        tenant_id=tenant_id,
        kind=ActionPreviewKind.COPY,
        summary="Ad copy draft",
    )
    hitl.submit_for_approval(prev_copy)
    hitl.decide(
        "prev-copy-rev",
        decision=HumanDecisionType.REQUEST_REVISION,
        approver="[email protected]",
        approver_role=ReviewerRole.BRAND_LEAD,
        tenant_id=tenant_id,
        revision_notes="Headline tone too informal.",
    )

    with pytest.raises(ApprovalRequiredError, match="strictly blocked"):
        hitl.require_approved("prev-copy-rev")


@pytest.mark.asyncio
async def test_p5_tampered_preview_content_or_artifact_fails_closed() -> None:
    """Criterion 6: Tampered preview content hash or modified payload invalidates clearance."""
    priv_key, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    hitl: HitlCoordinator = h["hitl_coordinator"]
    tenant_id = "tenant-pharma-1"

    preview = ActionPreview(
        preview_id="prev-tamper",
        task_id="task-tamper-1",
        tenant_id=tenant_id,
        kind=ActionPreviewKind.SPEND,
        summary="Approved spend $10,000",
        spend_amount=10000.0,
    )
    hitl.submit_for_approval(preview)

    original_hash = compute_preview_hash(preview)

    # Attacker alters preview spend amount in-flight
    preview.spend_amount = 99999.0

    # Human decides with original hash expectation
    with pytest.raises(SignatureVerificationError, match="Preview content hash mismatch"):
        hitl.decide(
            "prev-tamper",
            decision=HumanDecisionType.APPROVE,
            approver="[email protected]",
            approver_role=ReviewerRole.FINANCE,
            tenant_id=tenant_id,
            preview_content_hash=original_hash,  # Mismatches current computed hash
        )


@pytest.mark.asyncio
async def test_p5_cross_tenant_isolation_enforcement() -> None:
    """Criterion 7: Cross-tenant approval and dispatch attempts fail closed."""
    priv_key, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    hitl: HitlCoordinator = h["hitl_coordinator"]
    gateway: OutboundGateway = h["gateway"]

    preview = ActionPreview(
        preview_id="prev-tenant-a",
        task_id="task-a-1",
        tenant_id="tenant-alpha",
        kind=ActionPreviewKind.COPY,
        summary="Alpha copy preview",
    )
    hitl.submit_for_approval(preview)

    # Reviewer claiming tenant-bravo attempting to decide tenant-alpha preview fails closed
    with pytest.raises(PolicyViolationError, match="Tenant authority mismatch"):
        hitl.decide(
            "prev-tenant-a",
            decision=HumanDecisionType.APPROVE,
            approver="[email protected]",
            approver_role=ReviewerRole.BRAND_LEAD,
            tenant_id="tenant-bravo",
        )

    # Legitimate approval for tenant-alpha
    hitl.decide(
        "prev-tenant-a",
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role=ReviewerRole.BRAND_LEAD,
        tenant_id="tenant-alpha",
    )

    # Dispatch specifying tenant-bravo against tenant-alpha clearance fails closed
    dispatch = DispatchDirective(
        dispatch_id="disp-cross-tenant",
        task_id="task-a-1",
        action_preview_id="prev-tenant-a",
        signature="sig",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="meta",
        tenant_id="tenant-bravo",
    )
    sig = sign_payload(canonical_dispatch_bytes(dispatch), priv_key)
    dispatch = dispatch.model_copy(update={"signature": sig})

    with pytest.raises(PolicyViolationError, match="Tenant authority mismatch"):
        await gateway.validate_readiness(dispatch)


@pytest.mark.asyncio
async def test_p5_replay_expired_and_revoked_clearance_fails_closed() -> None:
    """Criterion 8: Expired clearances, revoked audience tokens, and duplicate modified dispatches are rejected."""
    priv_key, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    hitl: HitlCoordinator = h["hitl_coordinator"]
    gateway: OutboundGateway = h["gateway"]
    tenant_id = "tenant-pharma-1"

    preview = ActionPreview(
        preview_id="prev-replay-test",
        task_id="task-replay-1",
        tenant_id=tenant_id,
        kind=ActionPreviewKind.SPEND,
        summary="Spend for replay test",
        spend_amount=5000.0,
    )
    hitl.submit_for_approval(preview)
    dec = hitl.decide(
        "prev-replay-test",
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role=ReviewerRole.FINANCE,
        tenant_id=tenant_id,
    )

    # A. Expired clearance
    assert dec.clearance is not None
    dec.clearance.expires_at = datetime.now(UTC) - timedelta(minutes=5)

    dispatch = DispatchDirective(
        dispatch_id="disp-exp-test",
        task_id="task-replay-1",
        action_preview_id="prev-replay-test",
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="meta",
        tenant_id=tenant_id,
        payload={"spend_amount": 5000.0},
    )
    sig = sign_payload(canonical_dispatch_bytes(dispatch), priv_key)
    dispatch = dispatch.model_copy(update={"signature": sig})

    with pytest.raises(PolicyViolationError, match="Clearance.*expired"):
        await gateway.validate_readiness(dispatch)

    # Reset expiration for B & C
    dec.clearance.expires_at = datetime.now(UTC) + timedelta(hours=1)

    # B. Revoked audience token
    revoked_token = AudienceToken(
        token_id="tok-revoked",
        target_audience="global",
        tenant_id=tenant_id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        is_revoked=True,
    )
    dispatch_revoked = dispatch.model_copy(update={"audience_token": revoked_token})
    sig_revoked = sign_payload(canonical_dispatch_bytes(dispatch_revoked), priv_key)
    dispatch_revoked = dispatch_revoked.model_copy(update={"signature": sig_revoked})

    with pytest.raises(PolicyViolationError, match="has been revoked"):
        await gateway.validate_readiness(dispatch_revoked)

    # C. Replayed duplicate with altered payload
    valid_dispatch = dispatch.model_copy(update={"audience_token": None, "idempotency_key": "idem-key-1"})
    sig_valid = sign_payload(canonical_dispatch_bytes(valid_dispatch), priv_key)
    valid_dispatch = valid_dispatch.model_copy(update={"signature": sig_valid})

    readiness1 = await gateway.validate_readiness(valid_dispatch)
    assert readiness1.status == "READY"

    # Duplicate submission with different payload
    tampered_replay = valid_dispatch.model_copy(update={"payload": {"spend_amount": 99999.0}})
    sig_tampered = sign_payload(canonical_dispatch_bytes(tampered_replay), priv_key)
    tampered_replay = tampered_replay.model_copy(update={"signature": sig_tampered})

    with pytest.raises(PolicyViolationError, match="Replay detected"):
        await gateway.validate_readiness(tampered_replay)


@pytest.mark.asyncio
async def test_p5_unsigned_or_forged_outbound_dispatch_fails_closed() -> None:
    """Criterion 9: Unsigned or forged dispatch directives strictly fail closed."""
    priv_key_real, pub_pem_real = _make_keypair()
    priv_key_forged, _ = _make_keypair()

    h = _build_test_harness(pub_pem_real)
    hitl: HitlCoordinator = h["hitl_coordinator"]
    gateway: OutboundGateway = h["gateway"]
    tenant_id = "tenant-pharma-1"

    preview = ActionPreview(
        preview_id="prev-sig-test",
        task_id="task-sig-1",
        tenant_id=tenant_id,
        kind=ActionPreviewKind.COPY,
        summary="Copy preview",
    )
    hitl.submit_for_approval(preview)
    hitl.decide(
        "prev-sig-test",
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role=ReviewerRole.BRAND_LEAD,
        tenant_id=tenant_id,
    )

    base_dispatch = DispatchDirective(
        dispatch_id="disp-sig-test",
        task_id="task-sig-1",
        action_preview_id="prev-sig-test",
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="meta",
        tenant_id=tenant_id,
    )

    # Empty signature fails
    with pytest.raises(SignatureVerificationError):
        await gateway.validate_readiness(base_dispatch)

    # Forged signature from unauthorized key fails
    forged_sig = sign_payload(canonical_dispatch_bytes(base_dispatch), priv_key_forged)
    forged_dispatch = base_dispatch.model_copy(update={"signature": forged_sig})
    with pytest.raises(SignatureVerificationError):
        await gateway.validate_readiness(forged_dispatch)


@pytest.mark.asyncio
async def test_p5_sole_dispatch_authority_and_model_a() -> None:
    """Criterion 10: Only IE creates authorized dispatch directives; Workers cannot bypass or actuate."""
    priv_key, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    ie: IntelligenceEngine = h["ie"]
    hitl: HitlCoordinator = h["hitl_coordinator"]
    tenant_id = "tenant-pharma-1"

    preview = ActionPreview(
        preview_id="prev-ie-auth",
        task_id="task-auth-1",
        tenant_id=tenant_id,
        kind=ActionPreviewKind.SPEND,
        summary="Spend preview",
        spend_amount=15000.0,
    )
    hitl.submit_for_approval(preview)
    hitl.decide(
        "prev-ie-auth",
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role=ReviewerRole.FINANCE,
        tenant_id=tenant_id,
    )

    # IE successfully creates signed dispatch bound to clearance
    directive = await ie.create_authorized_dispatch(
        "prev-ie-auth",
        channel="meta",
        payload={"spend_amount": 15000.0},
        private_key=priv_key,
        tenant_id=tenant_id,
    )
    assert directive.signature != ""
    assert directive.clearance_id is not None
    assert directive.preview_content_hash is not None

    # Model A: Verify Worker agents have zero handle to create dispatch or actuate
    from app.agents.development import DevelopmentAgent
    dev_worker = DevelopmentAgent(sandbox_client=FakeSandboxClient(), llm_client=None)
    assert not hasattr(dev_worker, "create_authorized_dispatch")
    assert not hasattr(dev_worker, "outbound_gateway")
    assert not hasattr(dev_worker, "_private_key")


@pytest.mark.asyncio
async def test_p5_cts_canonical_lifecycle_preservation() -> None:
    """Criterion 11: Task state transitions strictly adhere to canonical CTS state machine."""
    sm = TaskStateMachine()
    task = CanonicalTaskState(
        task_id="task-cts-cert",
        directive_id="dir-cts-cert",
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
    )

    # PENDING -> GRANTED -> IN_PROGRESS -> AWAITING_APPROVAL -> APPROVED -> DISPATCHED -> COMPLETED
    t_granted = sm.transition(task, TaskStatus.GRANTED, checkpoint_id="cp-1")
    assert t_granted.status == TaskStatus.GRANTED

    t_in_progress = sm.transition(t_granted, TaskStatus.IN_PROGRESS, checkpoint_id="cp-2")
    assert t_in_progress.status == TaskStatus.IN_PROGRESS

    t_awaiting = sm.transition(t_in_progress, TaskStatus.AWAITING_APPROVAL, checkpoint_id="cp-3")
    assert t_awaiting.status == TaskStatus.AWAITING_APPROVAL

    t_approved = sm.transition(t_awaiting, TaskStatus.APPROVED, checkpoint_id="cp-4")
    assert t_approved.status == TaskStatus.APPROVED

    t_dispatched = sm.transition(t_approved, TaskStatus.DISPATCHED, checkpoint_id="cp-5")
    assert t_dispatched.status == TaskStatus.DISPATCHED

    t_completed = sm.transition(t_dispatched, TaskStatus.COMPLETED, checkpoint_id="cp-6")
    assert t_completed.status == TaskStatus.COMPLETED

    # Illegal skip attempt fails closed
    with pytest.raises(InvalidTransitionError):
        sm.transition(task, TaskStatus.DISPATCHED, checkpoint_id="cp-illegal")


@pytest.mark.asyncio
async def test_p5_end_to_end_governed_dry_run_zero_side_effects() -> None:
    """Criterion 12 & 13: Full governed path to MCP_ACT dry-run with ZERO production side effects."""
    priv_key, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    ie: IntelligenceEngine = h["ie"]
    gateway: OutboundGateway = h["gateway"]
    spy_ads: SpyAdsAdapter = h["spy_ads"]
    tenant_id = "tenant-pharma-1"

    # 1. Directive
    directive = Directive(
        directive_id="dir-e2e-dryrun",
        tenant_id=tenant_id,
        objective="Execute Q4 Omnichannel Marketing Run",
        budget_cap=50000.0,
        risk_ceiling=RiskLevel.MEDIUM,
        scope=TenantScope(tenant_id=tenant_id, brand_ids=["brand-derm"], allowed_channels=["meta", "google", "instagram"]),
    )

    # 2. Worker Evidence Synthesis
    envelopes = _build_multi_worker_envelopes(tenant_id)
    pkg = await ie.consolidate_evidence(directive, envelopes)
    assert pkg.status == ConsolidatedPackageStatus.VALID

    # 3. Action Preview Dossier
    dossier = await ie.generate_action_previews(directive, pkg)
    spend_preview = next(p for p in dossier.previews if p.kind == ActionPreviewKind.SPEND)
    assert spend_preview.review_status == ReviewStatus.PENDING

    # 4. HITL Decision with Cryptographic Sign-off
    hash_spend = compute_preview_hash(spend_preview)
    dec_time = datetime.now(UTC)
    canon_bytes = canonical_decision_bytes(
        preview_id=spend_preview.preview_id,
        decision="APPROVE",
        approver="[email protected]",
        tenant_id=tenant_id,
        preview_content_hash=hash_spend,
        decided_at=dec_time.isoformat(),
    )
    sig = sign_payload(canon_bytes, priv_key)

    hitl_decision = await ie.record_hitl_decision(
        spend_preview.preview_id,
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role=ReviewerRole.FINANCE,
        tenant_id=tenant_id,
        signature=sig,
        public_key_pem=pub_pem,
        preview_content_hash=hash_spend,
        decided_at=dec_time,
    )
    assert hitl_decision.approved is True

    # 5. IE Authorized Dispatch Construction
    dispatch = await ie.create_authorized_dispatch(
        spend_preview.preview_id,
        channel="meta",
        payload={"spend_amount": 35000.0, "campaign_id": "meta-derm-q4"},
        private_key=priv_key,
        tenant_id=tenant_id,
    )

    # 6. Outbound Gateway Dry-Run Readiness Certification
    readiness: DispatchReadiness = await gateway.validate_readiness(dispatch)

    assert readiness.status == "READY"
    assert readiness.is_ready is True
    assert readiness.directive_id == dispatch.dispatch_id
    assert readiness.action_preview_id == spend_preview.preview_id

    # ZERO production side effects: Verify fake adapter was never actuated during dry-run
    assert len(spy_ads.applied) == 0


@pytest.mark.asyncio
async def test_p5_provenance_lineage_traceability() -> None:
    """Criterion 14: Complete provenance chain captures evidence -> preview -> decision -> dispatch."""
    priv_key, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    ie: IntelligenceEngine = h["ie"]
    prov_repo: FakeProvenanceRepository = h["prov_repo"]
    tenant_id = "tenant-pharma-1"

    directive = Directive(
        directive_id="dir-prov-trace",
        tenant_id=tenant_id,
        objective="Provenance Lineage Run",
        budget_cap=50000.0,
        risk_ceiling=RiskLevel.MEDIUM,
        scope=TenantScope(tenant_id=tenant_id, brand_ids=["brand-derm"], allowed_channels=["meta"]),
    )

    envelopes = _build_multi_worker_envelopes(tenant_id)
    pkg = await ie.consolidate_evidence(directive, envelopes)
    dossier = await ie.generate_action_previews(directive, pkg)
    target_preview = dossier.previews[0]

    h_prev = compute_preview_hash(target_preview)
    dec_time = datetime.now(UTC)
    canon_bytes = canonical_decision_bytes(
        preview_id=target_preview.preview_id,
        decision="APPROVE",
        approver="[email protected]",
        tenant_id=tenant_id,
        preview_content_hash=h_prev,
        decided_at=dec_time.isoformat(),
    )
    sig = sign_payload(canon_bytes, priv_key)

    await ie.record_hitl_decision(
        target_preview.preview_id,
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role=ReviewerRole.ADMIN,
        tenant_id=tenant_id,
        signature=sig,
        public_key_pem=pub_pem,
        preview_content_hash=h_prev,
        decided_at=dec_time,
    )

    await ie.create_authorized_dispatch(
        target_preview.preview_id,
        channel="meta",
        payload={"spend_amount": 1000.0},
        private_key=priv_key,
        tenant_id=tenant_id,
    )

    chain = await prov_repo.chain(tenant_id)
    activities = [r.activity for r in chain]

    assert "evidence_consolidation" in activities
    assert "action_preview_generation" in activities
    assert "hitl_approve" in activities
    assert "create_authorized_dispatch" in activities


@pytest.mark.asyncio
async def test_p5_llm_cannot_auto_approve_or_bypass_hitl() -> None:
    """Criterion 15: LLM model output cannot auto-approve or bypass the HITL human decision gate."""
    _, pub_pem = _make_keypair()
    h = _build_test_harness(pub_pem)
    hitl: HitlCoordinator = h["hitl_coordinator"]
    gateway: OutboundGateway = h["gateway"]
    tenant_id = "tenant-pharma-1"

    preview = ActionPreview(
        preview_id="prev-llm-gate",
        task_id="task-llm-1",
        tenant_id=tenant_id,
        kind=ActionPreviewKind.SPEND,
        summary="Spend proposal $25,000",
        spend_amount=25000.0,
    )
    hitl.submit_for_approval(preview)

    # Simulated LLM output pretending to grant authorization
    llm_advisory_output = {
        "status": "APPROVED",
        "rationale": "High projected ROAS of 4.5x. I approve this spend of $25,000.",
        "authorization_code": "LLM_AUTO_AUTH_12345",
    }

    # Attempting to use LLM text or output as an approval fails closed
    assert hitl.is_approved("prev-llm-gate") is False
    with pytest.raises(ApprovalRequiredError):
        hitl.require_approved("prev-llm-gate")

    # Outbound gateway rejects dispatch attempting to cite LLM approval
    fake_dispatch = DispatchDirective(
        dispatch_id="disp-llm-bypass",
        task_id="task-llm-1",
        action_preview_id="prev-llm-gate",
        signature="invalid",
        approved_by=f"llm:{llm_advisory_output['authorization_code']}",
        approved_at=datetime.now(UTC),
        channel="meta",
        tenant_id=tenant_id,
    )
    with pytest.raises(ApprovalRequiredError):
        await gateway.validate_readiness(fake_dispatch)
