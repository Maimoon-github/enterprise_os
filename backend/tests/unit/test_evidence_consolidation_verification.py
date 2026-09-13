"""Comprehensive verification suite for T22 Evidence Envelope Consolidation & Confidence Verification."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer, SynthesizedEvidence
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import ActionPreviewKind
from app.schemas.agent_contracts import (
    AdCopyVariant,
    CandidateStateDelta,
    ChannelAllocation,
    CodeDiffEntry,
    ConfidenceInterval,
    ConflictSeverity,
    ConsolidatedEvidencePackage,
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
    flagged_claims: list[str] | None = None,
    extra_channels: list[str] | None = None,
) -> EvidenceEnvelope:
    channels = ["meta", "google"] + (extra_channels or [])
    copy_variants = [
        AdCopyVariant(
            variant_id=f"var-{ch}",
            channel=ch,
            headline=f"Top rated performance on {ch}",
            body_copy="Clinically proven formula with noticeable results in 14 days.",
            source_claim_ids=["claim-clin-101"],
        )
        for ch in channels
    ]
    schedules = [
        ContentScheduleItem(
            schedule_id=f"sched-{ch}",
            day_or_week="Week 1",
            channel=ch,
            variant_ref=f"var-{ch}",
            primary_objective="Acquisition",
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
        schedules=schedules,
        approved_claim_refs=["claim-clin-101"],
        flagged_unsupported_claims=flagged_claims or [],
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
    security_passed: bool = True,
    syntax_errors: list[str] | None = None,
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
                diff_unified="--- a/showcase.py\n+++ b/showcase.py\n@@ -1 +1 @@\n-# old\n+# new",
                syntax_errors=syntax_errors or [],
            )
        ],
        changed_files=["components/showcase.py"],
        security_checks_passed=security_passed,
    )
    return EvidenceEnvelope(
        task_id=task_id,
        worker_role=WorkerRole.DEVELOPMENT,
        confidence=ConfidenceInterval(point_estimate=0.92, lower_bound=0.88, upper_bound=0.96),
        evidence=["Synthesized responsive ProductShowcase UI template.", "Unified AST-validated code diff generated."],
        findings=["UI templates generated", "Code diff validated"],
        generated_artifacts=[f"dev:{task_id}", f"diff:{task_id}"],
        payload={"dev_deliverable": deliv.model_dump_json(), "diff": deliv.code_diffs[0].diff_unified},
        provenance={
            "agent": "development",
            "capability": "code_diff",
            "task_id": task_id,
            "execution_id": f"exec-{task_id}",
            "tenant_id": tenant_id,
        },
        proposed_state_changes={"status": "completed", "capability": "code_diff"},
    )


# =========================================================================
# Unit Tests
# =========================================================================

def test_valid_t19_t20_t21_consolidation() -> None:
    """Valid T19 (strategy), T20 (creative), and T21 (development) envelopes produce a valid package."""
    synthesizer = EvidenceSynthesizer()
    strat_env = _make_strategy_envelope()
    creat_env = _make_creative_envelope()
    dev_env = _make_development_envelope()

    package = synthesizer.consolidate(
        [strat_env, creat_env, dev_env],
        expected_tenant_id="tenant-alpha",
        required_roles=[WorkerRole.STRATEGY, WorkerRole.CREATIVE_CONTENT, WorkerRole.DEVELOPMENT],
    )

    assert package.status == ConsolidatedPackageStatus.VALID
    assert len(package.rejected_items) == 0
    assert len(package.conflicts) == 0
    assert len(package.source_task_ids) == 3
    assert set(package.participating_roles) == {
        WorkerRole.STRATEGY,
        WorkerRole.CREATIVE_CONTENT,
        WorkerRole.DEVELOPMENT,
    }

    # Artifact references
    artifact_ids = [a["artifact_id"] for a in package.validated_artifacts]
    assert "strategy:task-strat-1" in artifact_ids
    assert "creative:task-creat-1" in artifact_ids
    assert "dev:task-dev-1" in artifact_ids

    # Confidence summary
    assert package.confidence_summary.confidence_band == "HIGH"
    assert package.confidence_summary.weighted_point_estimate >= 0.88
    assert package.confidence_summary.is_statistically_sound is True
    assert package.confidence_summary.envelope_count == 3

    # Candidate state deltas
    assert len(package.proposed_state_deltas) == 3
    assert all(d.is_authorized is True for d in package.proposed_state_deltas)
    assert all(d.target_status == "completed" for d in package.proposed_state_deltas)


def test_missing_prerequisite_role_flagged() -> None:
    """Consolidation with a missing required worker role records a blocking conflict."""
    synthesizer = EvidenceSynthesizer()
    strat_env = _make_strategy_envelope()
    creat_env = _make_creative_envelope()

    # Development is required but omitted
    package = synthesizer.consolidate(
        [strat_env, creat_env],
        expected_tenant_id="tenant-alpha",
        required_roles=[WorkerRole.STRATEGY, WorkerRole.CREATIVE_CONTENT, WorkerRole.DEVELOPMENT],
    )

    assert package.status == ConsolidatedPackageStatus.FLAGGED_WITH_CONFLICTS
    assert any(c.conflict_type == "missing_prerequisite_role" for c in package.conflicts)
    assert any("W_DEV" in c.description for c in package.conflicts)


def test_cross_tenant_envelope_rejected() -> None:
    """Envelope from a foreign tenant is rejected with CROSS_TENANT_BREACH and excluded."""
    synthesizer = EvidenceSynthesizer()
    strat_env = _make_strategy_envelope(tenant_id="tenant-alpha")
    foreign_creat_env = _make_creative_envelope(tenant_id="tenant-bravo", task_id="task-creat-breach")

    package = synthesizer.consolidate(
        [strat_env, foreign_creat_env],
        expected_tenant_id="tenant-alpha",
    )

    assert len(package.rejected_items) == 1
    rejected = package.rejected_items[0]
    assert rejected.task_id == "task-creat-breach"
    assert rejected.rejection_code == "CROSS_TENANT_BREACH"
    assert "tenant-bravo" in rejected.rejection_reason

    # Only tenant-alpha task was consolidated
    assert package.source_task_ids == ["task-strat-1"]


def test_malformed_confidence_rejected() -> None:
    """Envelope with inverted confidence bounds (lower > upper) is rejected with MALFORMED_CONFIDENCE."""
    synthesizer = EvidenceSynthesizer()
    strat_env = _make_strategy_envelope()
    strat_env.confidence = ConfidenceInterval(point_estimate=0.8, lower_bound=0.9, upper_bound=0.7)  # Inverted

    package = synthesizer.consolidate([strat_env], expected_tenant_id="tenant-alpha")

    assert len(package.rejected_items) == 1
    rejected = package.rejected_items[0]
    assert rejected.rejection_code == "MALFORMED_CONFIDENCE"
    assert package.status == ConsolidatedPackageStatus.REJECTED


def test_out_of_bounds_confidence_rejected() -> None:
    """Confidence point estimate > 1.0 or < 0.0 is rejected."""
    synthesizer = EvidenceSynthesizer()
    strat_env = _make_strategy_envelope()
    strat_env.confidence = ConfidenceInterval(point_estimate=1.25, lower_bound=0.8, upper_bound=1.0)

    package = synthesizer.consolidate([strat_env], expected_tenant_id="tenant-alpha")

    assert len(package.rejected_items) == 1
    assert package.rejected_items[0].rejection_code == "MALFORMED_CONFIDENCE"


def test_detects_channel_contradiction_between_strategy_and_creative() -> None:
    """Creative assets targeting channels with no budget in strategy produce a surfaced conflict."""
    synthesizer = EvidenceSynthesizer()
    strat_env = _make_strategy_envelope()  # Meta & Google only
    # Creative adds TikTok which has zero budget in strategy
    creat_env = _make_creative_envelope(extra_channels=["tiktok"])

    package = synthesizer.consolidate([strat_env, creat_env], expected_tenant_id="tenant-alpha")

    assert package.status == ConsolidatedPackageStatus.FLAGGED_WITH_CONFLICTS
    assert any(c.conflict_type == "channel_allocation_mismatch" for c in package.conflicts)
    conflict = next(c for c in package.conflicts if c.conflict_type == "channel_allocation_mismatch")
    assert "tiktok" in conflict.description
    assert conflict.severity == ConflictSeverity.WARNING
    assert conflict.resolvable_by_hitl is True


def test_detects_unsupported_claims_conflict() -> None:
    """Flagged unsupported claims in creative package generate a BLOCKING conflict."""
    synthesizer = EvidenceSynthesizer()
    strat_env = _make_strategy_envelope()
    creat_env = _make_creative_envelope(flagged_claims=["claim-unverified-cure-99"])

    package = synthesizer.consolidate([strat_env, creat_env], expected_tenant_id="tenant-alpha")

    assert package.status == ConsolidatedPackageStatus.FLAGGED_WITH_CONFLICTS
    assert any(c.conflict_type == "unsupported_claims_detected" for c in package.conflicts)
    conflict = next(c for c in package.conflicts if c.conflict_type == "unsupported_claims_detected")
    assert conflict.severity == ConflictSeverity.BLOCKING


def test_detects_duplicate_task_id_and_stale_evidence() -> None:
    """Multiple envelopes with duplicate task IDs surface a conflict without silent overwrite."""
    synthesizer = EvidenceSynthesizer()
    strat_env_1 = _make_strategy_envelope(task_id="task-strat-dup")
    strat_env_2 = _make_strategy_envelope(task_id="task-strat-dup")

    package = synthesizer.consolidate([strat_env_1, strat_env_2], expected_tenant_id="tenant-alpha")

    assert any(c.conflict_type == "duplicate_task_evidence" for c in package.conflicts)
    conflict = next(c for c in package.conflicts if c.conflict_type == "duplicate_task_evidence")
    assert conflict.conflicting_task_ids == ["task-strat-dup"]


def test_detects_security_failure_in_development_diff() -> None:
    """Security check failure in development code diff produces a BLOCKING conflict."""
    synthesizer = EvidenceSynthesizer()
    dev_env = _make_development_envelope(security_passed=False)

    package = synthesizer.consolidate([dev_env], expected_tenant_id="tenant-alpha")

    assert package.status == ConsolidatedPackageStatus.FLAGGED_WITH_CONFLICTS
    assert any(c.conflict_type == "security_check_failed" for c in package.conflicts)
    conflict = next(c for c in package.conflicts if c.conflict_type == "security_check_failed")
    assert conflict.severity == ConflictSeverity.BLOCKING
    assert conflict.resolvable_by_hitl is False


def test_consolidation_is_deterministic_and_idempotent() -> None:
    """Repeated consolidation invocations on identical inputs yield identical package hashes and results."""
    synthesizer = EvidenceSynthesizer()
    strat_env = _make_strategy_envelope()
    creat_env = _make_creative_envelope()
    dev_env = _make_development_envelope()

    pkg_1 = synthesizer.consolidate([strat_env, creat_env, dev_env], expected_tenant_id="tenant-alpha")
    pkg_2 = synthesizer.consolidate([strat_env, creat_env, dev_env], expected_tenant_id="tenant-alpha")

    assert pkg_1.package_id == pkg_2.package_id
    assert pkg_1.confidence_summary.weighted_point_estimate == pkg_2.confidence_summary.weighted_point_estimate
    assert pkg_1.source_task_ids == pkg_2.source_task_ids
    assert len(pkg_1.validated_artifacts) == len(pkg_2.validated_artifacts)


def test_legacy_synthesize_compatibility() -> None:
    """EvidenceSynthesizer.synthesize retains full backward compatibility."""
    synthesizer = EvidenceSynthesizer()
    strat_env = _make_strategy_envelope()
    creat_env = _make_creative_envelope()

    synthesized = synthesizer.synthesize([strat_env, creat_env])
    assert isinstance(synthesized, SynthesizedEvidence)
    assert synthesized.task_id == strat_env.task_id
    assert len(synthesized.evidence) > 0
    assert 0.88 <= synthesized.confidence.point_estimate <= 0.90


@pytest.mark.asyncio
async def test_intelligence_engine_consolidate_evidence_pipeline() -> None:
    """IntelligenceEngine.consolidate_evidence executes full consolidation and records audit provenance."""
    fake_prov = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(fake_prov)
    hitl_coordinator = HitlCoordinator()

    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=None,  # type: ignore[arg-type]
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=hitl_coordinator,
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

    strat_env = _make_strategy_envelope(tenant_id="tenant-alpha")
    creat_env = _make_creative_envelope(tenant_id="tenant-alpha")
    dev_env = _make_development_envelope(tenant_id="tenant-alpha")

    # 1. Consolidate evidence package
    package = await engine.consolidate_evidence(
        directive,
        [strat_env, creat_env, dev_env],
        required_roles=[WorkerRole.STRATEGY, WorkerRole.CREATIVE_CONTENT, WorkerRole.DEVELOPMENT],
    )

    assert package.status == ConsolidatedPackageStatus.VALID
    assert package.tenant_id == "tenant-alpha"

    # Provenance audit recorded
    prov_records = fake_prov._chains.get("tenant-alpha", [])
    assert any(r.activity == "evidence_consolidation" for r in prov_records)

    # 2. Downstream T23 Preview generation directly from ConsolidatedEvidencePackage
    preview = await engine.build_preview(
        package,
        kind=ActionPreviewKind.SPEND,
        risk_level=RiskLevel.LOW,
        spend_amount=45000.0,
    )
    assert preview.requires_approval is True
    assert preview.spend_amount == 45000.0
    assert hitl_coordinator.is_pending(preview.preview_id)
