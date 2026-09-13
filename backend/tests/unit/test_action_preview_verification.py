"""Comprehensive verification suite for T23 Structured Action Preview Generation."""

from __future__ import annotations

import pytest

from app.core.exceptions import PolicyViolationError
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import (
    ActionPreviewDossier,
    ActionPreviewKind,
    ReviewStatus,
)
from app.schemas.agent_contracts import (
    AdCopyVariant,
    CandidateStateDelta,
    ChannelAllocation,
    CodeDiffEntry,
    ConfidenceInterval,
    ConflictSeverity,
    ConsolidatedConfidenceSummary,
    ConsolidatedEvidencePackage,
    ConsolidatedPackageStatus,
    ContentScheduleItem,
    CreativePackage,
    DevelopmentDeliverable,
    EvidenceConflict,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    SocialPostVariant,
    UITemplateDefinition,
    VisualBrief,
)
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.services.hitl import HitlCoordinator
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository


def _make_strategy_envelope(tenant_id: str = "tenant-alpha", task_id: str = "task-strat-1") -> EvidenceEnvelope:
    plan = OmnichannelStrategyPlan(
        plan_id="plan-1",
        tenant_id=tenant_id,
        brand_id="brand-1",
        budget_ceiling=50000.0,
        total_allocated=45000.0,
        unallocated_contingency=5000.0,
        channel_allocations=[
            ChannelAllocation(channel="meta", allocated_amount=25000.0, percentage_of_total=55.5),
            ChannelAllocation(channel="google", allocated_amount=20000.0, percentage_of_total=44.5),
        ],
        approved_claims_applied=["claim-clin-101", "claim-fast-202"],
    )
    return EvidenceEnvelope(
        task_id=task_id,
        worker_role=WorkerRole.STRATEGY,
        confidence=ConfidenceInterval(point_estimate=0.90, lower_bound=0.85, upper_bound=0.95),
        evidence=["Omnichannel budget allocated: $45000 across Meta and Google.", "Target ROAS: 2.8x blended."],
        findings=["Omnichannel roadmap validated", "Contingency reserve established"],
        generated_artifacts=[f"strategy:{task_id}", f"alloc:{task_id}"],
        payload={"strategy_plan": plan.model_dump_json(), "budget_total": "45000.0"},
        provenance={
            "agent": "strategy",
            "capability": "allocation",
            "task_id": task_id,
            "execution_id": f"exec-{task_id}",
            "tenant_id": tenant_id,
        },
        proposed_state_changes={"status": "completed", "capability": "allocation"},
    )


def _make_creative_envelope(
    tenant_id: str = "tenant-alpha",
    task_id: str = "task-creat-1",
    body_copy: str = "Clinically proven formula with noticeable results in 14 days.",
) -> EvidenceEnvelope:
    channels = ["meta", "google"]
    copy_variants = [
        AdCopyVariant(
            variant_id=f"var-{ch}",
            channel=ch,
            headline=f"Top rated performance on {ch}",
            body_copy=body_copy,
            source_claim_ids=["claim-clin-101"],
        )
        for ch in channels
    ]
    pkg = CreativePackage(
        package_id="pkg-creat-1",
        tenant_id=tenant_id,
        brand_id="brand-1",
        objective="Drive Q4 acquisition",
        ad_copy_variants=copy_variants,
        social_posts=[
            SocialPostVariant(
                post_id="post-1",
                platform=channels[0],
                hook="Looking for real results?",
                caption="Here is why dermatologists recommend it.",
                source_claim_ids=["claim-clin-101"],
            )
        ],
        visual_briefs=[
            VisualBrief(
                brief_id="brief-1",
                asset_title="Serum Bottle Hero",
                channel=channels[0],
                art_direction="Clean minimalist studio lighting",
            )
        ],
        schedules=[
            ContentScheduleItem(
                schedule_id=f"sched-{ch}",
                day_or_week="Week 1",
                channel=ch,
                variant_ref=f"var-{ch}",
                primary_objective="Acquisition",
            )
            for ch in channels
        ],
        approved_claim_refs=["claim-clin-101"],
    )
    return EvidenceEnvelope(
        task_id=task_id,
        worker_role=WorkerRole.CREATIVE_CONTENT,
        confidence=ConfidenceInterval(point_estimate=0.88, lower_bound=0.82, upper_bound=0.94),
        evidence=["Generated 2 ad copy variants and 1 visual brief.", "Claim references validated against T16 dossier."],
        findings=["Multi-channel copy generated", "Visual briefs synthesized"],
        generated_artifacts=[f"creative:{task_id}", f"copy:{task_id}"],
        payload={"creative_package": pkg.model_dump_json()},
        provenance={
            "agent": "creative",
            "capability": "copywriting",
            "task_id": task_id,
            "execution_id": f"exec-{task_id}",
            "tenant_id": tenant_id,
        },
        proposed_state_changes={"status": "completed", "capability": "copywriting"},
    )


def _make_development_envelope(
    tenant_id: str = "tenant-alpha",
    task_id: str = "task-dev-1",
    diff_content: str = "--- a/showcase.py\n+++ b/showcase.py\n@@ -1 +1 @@\n-# old\n+# new",
) -> EvidenceEnvelope:
    deliv = DevelopmentDeliverable(
        deliverable_id="deliv-dev-1",
        tenant_id=tenant_id,
        task_id=task_id,
        component_name="ProductShowcase",
        ui_templates=[
            UITemplateDefinition(
                template_id="tmpl-1",
                name="ProductShowcase",
                template_markup="<section class='showcase'><h1>Serum</h1></section>",
                css_styles=".showcase { display: flex; }",
            )
        ],
        code_diffs=[
            CodeDiffEntry(
                file_path="components/showcase.py",
                diff_unified=diff_content,
            )
        ],
        changed_files=["components/showcase.py"],
        security_checks_passed=True,
    )
    return EvidenceEnvelope(
        task_id=task_id,
        worker_role=WorkerRole.DEVELOPMENT,
        confidence=ConfidenceInterval(point_estimate=0.92, lower_bound=0.88, upper_bound=0.96),
        evidence=["Synthesized responsive ProductShowcase UI template.", "Unified AST-validated code diff generated."],
        findings=["UI templates generated", "Code diff validated"],
        generated_artifacts=[f"dev:{task_id}", f"diff:{task_id}"],
        payload={"dev_deliverable": deliv.model_dump_json(), "diff": diff_content},
        provenance={
            "agent": "development",
            "capability": "code_diff",
            "task_id": task_id,
            "execution_id": f"exec-{task_id}",
            "tenant_id": tenant_id,
        },
        proposed_state_changes={"status": "completed", "capability": "code_diff"},
    )


def _build_test_consolidated_package(tenant_id: str = "tenant-alpha") -> ConsolidatedEvidencePackage:
    synthesizer = EvidenceSynthesizer()
    strat_env = _make_strategy_envelope(tenant_id)
    creat_env = _make_creative_envelope(tenant_id)
    dev_env = _make_development_envelope(tenant_id)
    return synthesizer.consolidate(
        [strat_env, creat_env, dev_env],
        expected_tenant_id=tenant_id,
        required_roles=[WorkerRole.STRATEGY, WorkerRole.CREATIVE_CONTENT, WorkerRole.DEVELOPMENT],
    )


# =========================================================================
# Unit Tests
# =========================================================================

def test_generate_valid_four_type_dossier() -> None:
    """Consolidates T22 package into SPEND, CLAIM, COPY, and CODE_DIFF action previews."""
    generator = HitlPreviewGenerator()
    package = _build_test_consolidated_package()

    dossier = generator.generate_dossier(package, risk_level=RiskLevel.MEDIUM)

    assert isinstance(dossier, ActionPreviewDossier)
    assert dossier.tenant_id == "tenant-alpha"
    assert dossier.source_package_id == package.package_id
    assert dossier.preview_count == 4
    assert set(dossier.categories) == {
        ActionPreviewKind.SPEND,
        ActionPreviewKind.CLAIM,
        ActionPreviewKind.COPY,
        ActionPreviewKind.CODE_DIFF,
    }

    # Verify SPEND
    spend_prev = next(p for p in dossier.previews if p.kind == ActionPreviewKind.SPEND)
    assert spend_prev.spend_details is not None
    assert spend_prev.spend_amount == 45000.0
    assert spend_prev.spend_details.currency == "USD"
    assert spend_prev.requires_approval is True
    assert spend_prev.review_status == ReviewStatus.PENDING

    # Verify CLAIM
    claim_prev = next(p for p in dossier.previews if p.kind == ActionPreviewKind.CLAIM)
    assert claim_prev.claim_details is not None
    assert claim_prev.claim_details.validation_status == "SUPPORTED"
    assert claim_prev.requires_approval is True
    assert claim_prev.review_status == ReviewStatus.PENDING

    # Verify COPY
    copy_prev = next(p for p in dossier.previews if p.kind == ActionPreviewKind.COPY)
    assert copy_prev.copy_details is not None
    assert copy_prev.copy_details.call_to_action == "Shop Now"
    assert copy_prev.requires_approval is True
    assert copy_prev.review_status == ReviewStatus.PENDING

    # Verify CODE_DIFF
    diff_prev = next(p for p in dossier.previews if p.kind == ActionPreviewKind.CODE_DIFF)
    assert diff_prev.code_details is not None
    assert diff_prev.code_details.file_path == "components/showcase.py"
    assert diff_prev.diff is not None
    assert diff_prev.requires_approval is True
    assert diff_prev.review_status == ReviewStatus.PENDING


def test_missing_or_rejected_t22_fails_closed() -> None:
    """Generating action previews from a REJECTED T22 package fails closed."""
    generator = HitlPreviewGenerator()
    package = _build_test_consolidated_package()
    rejected_pkg = package.model_copy(update={"status": ConsolidatedPackageStatus.REJECTED})

    with pytest.raises(ValueError, match="Cannot generate action previews from a REJECTED evidence package"):
        generator.generate_dossier(rejected_pkg)


def test_cross_tenant_preview_rejection() -> None:
    """Directive tenant mismatch against package tenant raises PolicyViolationError in engine."""
    generator = HitlPreviewGenerator()
    coordinator = HitlCoordinator()
    fake_prov = FakeProvenanceRepository()

    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=None,  # type: ignore[arg-type]
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=generator,
        hitl_coordinator=coordinator,
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=ProvenanceRecorder(fake_prov),
        workers={},
    )

    package = _build_test_consolidated_package(tenant_id="tenant-alpha")
    foreign_directive = Directive(
        directive_id="dir-foreign-1",
        tenant_id="tenant-bravo",  # Mismatch
        scope=TenantScope(tenant_id="tenant-bravo", brand_id="brand-1"),
        objective="Cross tenant attempt",
        budget_cap=50000.0,
    )

    with pytest.raises(PolicyViolationError, match="Directive tenant 'tenant-bravo' does not match package tenant 'tenant-alpha'"):
        import asyncio
        asyncio.run(engine.generate_action_previews(foreign_directive, package))


def test_all_previews_start_strictly_pending() -> None:
    """All generated previews and the dossier strictly start in PENDING review status with approval required."""
    generator = HitlPreviewGenerator()
    package = _build_test_consolidated_package()

    dossier = generator.generate_dossier(package)

    assert dossier.review_status == ReviewStatus.PENDING
    for prev in dossier.previews:
        assert prev.review_status == ReviewStatus.PENDING
        assert prev.requires_approval is True


def test_untrusted_markup_sanitization() -> None:
    """Dangerous executable markup (<script>, javascript:, DOM event handlers) is neutralized."""
    generator = HitlPreviewGenerator()

    malicious_input = (
        "Super Serum <script>alert('xss')</script> click <a href='javascript:evil()'>here</a> "
        "or <img src='x' onerror='exploit()'/> for discounts."
    )

    sanitized = generator.sanitize_text(malicious_input)

    assert "<script>" not in sanitized
    assert "[SCRIPT_REMOVED]" in sanitized
    assert "javascript:" not in sanitized
    assert "[JS_REMOVED]:" in sanitized
    assert "onerror=" not in sanitized
    assert "data-blocked-handler=" in sanitized


def test_secret_leakage_redaction() -> None:
    """Secrets, API keys, private keys, and bearer tokens are redacted."""
    generator = HitlPreviewGenerator()

    secret_input = (
        "Debug info: api_key='sk-ant-api03-abcdef1234567890' and "
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    )

    sanitized = generator.sanitize_text(secret_input)

    assert "sk-ant-api03" not in sanitized
    assert "[REDACTED]" in sanitized


def test_deterministic_preview_generation() -> None:
    """Repeated preview dossier generation on identical package yields identical hashes and items."""
    generator = HitlPreviewGenerator()
    package = _build_test_consolidated_package()

    dossier_1 = generator.generate_dossier(package)
    dossier_2 = generator.generate_dossier(package)

    assert dossier_1.dossier_id == dossier_2.dossier_id
    assert dossier_1.preview_count == dossier_2.preview_count
    assert [p.preview_id for p in dossier_1.previews] == [p.preview_id for p in dossier_2.previews]
    assert dossier_1.total_spend_proposed == dossier_2.total_spend_proposed


def test_mutation_attempt_leaves_source_package_unchanged() -> None:
    """Generating previews does not mutate any fields or artifacts of the source package."""
    generator = HitlPreviewGenerator()
    package = _build_test_consolidated_package()
    snapshot_before = package.model_dump_json()

    _ = generator.generate_dossier(package)

    snapshot_after = package.model_dump_json()
    assert snapshot_before == snapshot_after


def test_surfaces_unresolved_conflicts_in_dossier() -> None:
    """Unresolved conflicts in T22 package are surfaced in critical_risks and warnings."""
    generator = HitlPreviewGenerator()
    package = _build_test_consolidated_package()

    # Inject a blocking conflict
    package_with_conflict = package.model_copy(
        update={
            "conflicts": [
                EvidenceConflict(
                    conflict_id="conf-1",
                    conflict_type="unsupported_claims_detected",
                    severity=ConflictSeverity.BLOCKING,
                    description="Unverified medical claim found in copy draft",
                )
            ]
        }
    )

    dossier = generator.generate_dossier(package_with_conflict)

    assert len(dossier.critical_risks) == 1
    assert "Unverified medical claim" in dossier.critical_risks[0]
    assert len(dossier.unresolved_conflicts) == 1


@pytest.mark.asyncio
async def test_intelligence_engine_generate_action_previews_pipeline() -> None:
    """IntelligenceEngine.generate_action_previews registers previews in HITL coordinator and records provenance."""
    fake_prov = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(fake_prov)
    coordinator = HitlCoordinator()

    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=None,  # type: ignore[arg-type]
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=coordinator,
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=provenance_recorder,
        workers={},
    )

    directive = Directive(
        directive_id="dir-campaign-1",
        tenant_id="tenant-alpha",
        scope=TenantScope(tenant_id="tenant-alpha", brand_id="brand-1"),
        objective="Q4 acquisition push",
        budget_cap=50000.0,
    )

    package = _build_test_consolidated_package(tenant_id="tenant-alpha")

    # Generate action previews
    dossier = await engine.generate_action_previews(directive, package)

    assert isinstance(dossier, ActionPreviewDossier)
    assert dossier.preview_count >= 4

    # Every preview is registered in HitlCoordinator as pending approval
    for prev in dossier.previews:
        assert coordinator.is_pending(prev.preview_id) is True

    # Provenance audit recorded
    records = fake_prov._chains.get("tenant-alpha", [])
    assert any(r.activity == "action_preview_generation" for r in records)


def test_backward_compatibility_single_preview_generation() -> None:
    """Existing HitlPreviewGenerator.generate method continues to function without regression."""
    from app.orchestration.evidence_synthesis import SynthesizedEvidence

    generator = HitlPreviewGenerator()
    evidence = SynthesizedEvidence(
        task_id="task-legacy-1",
        evidence=["Historical revenue evidence"],
        confidence=ConfidenceInterval(point_estimate=0.85, lower_bound=0.80, upper_bound=0.90),
    )

    prev = generator.generate(
        preview_id="prev-legacy-1",
        evidence=evidence,
        kind=ActionPreviewKind.SPEND,
        risk_level=RiskLevel.LOW,
        spend_amount=1000.0,
    )

    assert prev.preview_id == "prev-legacy-1"
    assert prev.kind == ActionPreviewKind.SPEND
    assert prev.spend_amount == 1000.0
    assert prev.requires_approval is True
    assert prev.review_status == ReviewStatus.PENDING
