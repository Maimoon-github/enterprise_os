"""Tests for LP-06: LEARN-QA Independent Quality Gate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest

from app.agents.learning_performance_engine.learning_performance import LearningPerformanceAgent
from app.agents.learning_performance_engine.subagents.quality import (
    LearningQualityAgent,
    compute_canonical_digest,
)
from app.schemas.agent_contracts import TaskGrant
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.learning_performance import (
    CalibrationProposal,
    EvidenceCategory,
    LearningDatasetManifest,
    LearningEstimate,
    LearningSpecialistResult,
    LearningUncertainty,
    QADecision,
    SpecialistStatus,
    UncertaintyKind,
)


def _make_grant(task_id: str = "task-t31-qa", tenant_id: str = "tenant-gamma") -> TaskGrant:
    return TaskGrant(
        task_id=task_id,
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id=tenant_id),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )


def _make_valid_specialist_result(
    role: str = "LEARN-ATTRIBUTION",
    tenant_id: str = "tenant-gamma",
    dataset_version: str = "1.0",
) -> LearningSpecialistResult:
    est = LearningEstimate(
        estimate_id=f"est-{role.lower()}-1",
        metric="attribution_weight",
        estimand="channel_weight",
        evidence_category=EvidenceCategory.OBSERVATIONAL,
        tenant_id=tenant_id,
        channel="meta",
        method_name="linear_attribution",
        point_estimate=0.45,
        units="ratio",
        uncertainty=LearningUncertainty(
            kind=UncertaintyKind.NOT_APPLICABLE,
            method="deterministic_point",
        ),
        causal_claim_permitted=False,
        diagnostics={"attributed_revenue": 450.0},
    )
    return LearningSpecialistResult(
        role=role,
        specialist_profile_id=f"learn.{role.lower().split('-')[-1]}.v1",
        attempt_id=f"att-{role.lower()}-1",
        dataset_version=dataset_version,
        status=SpecialistStatus.COMPLETE,
        estimates=[est],
        findings=["Valid touchpoint modeling executed."],
    )


# --- 1. Clean PASS flow ---

@pytest.mark.asyncio
async def test_learn_qa_pass_and_claim_allowlisting() -> None:
    agent = LearningQualityAgent()
    grant = _make_grant()
    res1 = _make_valid_specialist_result("LEARN-ATTRIBUTION")
    res2 = _make_valid_specialist_result("LEARN-DECAY")

    bundle = {
        "tenant_id": "tenant-gamma",
        "dataset_version": "1.0",
        "specialist_results": [res1, res2],
    }

    qa_result = await agent.run(grant, bundle)

    assert qa_result.decision == QADecision.PASS
    assert len(qa_result.accepted_claim_ids) == 2
    assert "est-learn-attribution-1" in qa_result.accepted_claim_ids
    assert "est-learn-decay-1" in qa_result.accepted_claim_ids
    assert not qa_result.rejected_claim_ids
    assert all(qa_result.deterministic_gate_results.values())
    assert len(qa_result.evidence_bundle_digest) == 64


# --- 2. Scope & Tenant Mismatch -> BLOCK ---

@pytest.mark.asyncio
async def test_learn_qa_blocks_on_scope_mismatch() -> None:
    agent = LearningQualityAgent()
    grant = _make_grant(tenant_id="tenant-gamma")
    # Off-tenant specialist estimate
    bad_res = _make_valid_specialist_result("LEARN-ATTRIBUTION", tenant_id="tenant-attacker")

    bundle = {
        "tenant_id": "tenant-gamma",
        "specialist_results": [bad_res],
    }

    qa_result = await agent.run(grant, bundle)

    assert qa_result.decision == QADecision.BLOCK
    assert "SCOPE_MISMATCH_ESTIMATE_est-learn-attribution-1" in qa_result.issue_codes
    assert not qa_result.accepted_claim_ids
    assert "est-learn-attribution-1" in qa_result.rejected_claim_ids


# --- 3. Causal Claim on Observational Evidence -> BLOCK ---

@pytest.mark.asyncio
async def test_learn_qa_blocks_on_unsupported_causal_claim() -> None:
    agent = LearningQualityAgent()
    grant = _make_grant()
    # Create estimate claiming causal validity in assumptions
    est = LearningEstimate(
        estimate_id="est-bad-causal-1",
        metric="lift",
        estimand="observational_lift",
        evidence_category=EvidenceCategory.OBSERVATIONAL,
        tenant_id="tenant-gamma",
        method_name="mmm_contribution",
        point_estimate=0.20,
        uncertainty=LearningUncertainty(kind=UncertaintyKind.NOT_APPLICABLE),
        causal_claim_permitted=False,
        assumptions=["This observational model proves causality for meta spend."],
    )
    res = LearningSpecialistResult(
        role="LEARN-ATTRIBUTION",
        specialist_profile_id="learn.attribution.v1",
        attempt_id="att-attr-bad",
        dataset_version="1.0",
        status=SpecialistStatus.COMPLETE,
        estimates=[est],
    )

    bundle = {"specialist_results": [res]}
    qa_result = await agent.run(grant, bundle)

    assert qa_result.decision == QADecision.BLOCK
    assert any("CAUSAL_LANGUAGE" in code for code in qa_result.issue_codes)
    assert not qa_result.accepted_claim_ids


# --- 4. Raw Data Leakage -> BLOCK ---

@pytest.mark.asyncio
async def test_learn_qa_blocks_on_raw_data_leakage() -> None:
    agent = LearningQualityAgent()
    grant = _make_grant()
    res = _make_valid_specialist_result("LEARN-FATIGUE")
    # Simulate accidental inclusion of secret token in findings
    res.findings.append("Encountered raw_events containing sk_live_secretkey12345 in attempt memory.")

    bundle = {"specialist_results": [res]}
    qa_result = await agent.run(grant, bundle)

    assert qa_result.decision == QADecision.BLOCK
    assert "RAW_DATA_OR_SECRET_LEAKAGE" in qa_result.issue_codes
    assert not qa_result.accepted_claim_ids


# --- 5. Same-Run Calibration Mutation -> BLOCK ---

@pytest.mark.asyncio
async def test_learn_qa_blocks_on_same_run_applied_calibration() -> None:
    agent = LearningQualityAgent()
    grant = _make_grant()
    res = _make_valid_specialist_result("LEARN-INCREMENTALITY")
    
    # We test bundle containing proposal marked applied
    now = datetime.now(UTC)
    unc = LearningUncertainty(kind=UncertaintyKind.CONFIDENCE_INTERVAL, lower_bound=0.01, upper_bound=0.05)
    
    # We bypass Pydantic model validator for test by creating a mock object or checking proposal gate
    class MockProposal:
        proposal_id = "cal-illegal-1"
        applied = True
        applicability_window_start = now
        applicability_window_end = now + timedelta(days=30)

    bundle = {
        "specialist_results": [res],
        "calibration_proposals": [MockProposal()],
    }
    qa_result = await agent.run(grant, bundle)

    assert qa_result.decision == QADecision.BLOCK
    assert "CALIBRATION_SAME_RUN_APPLIED_cal-illegal-1" in qa_result.issue_codes


# --- 6. Methodological Conflict -> REVISE ---

@pytest.mark.asyncio
async def test_learn_qa_emits_revise_on_unreconciled_conflict() -> None:
    agent = LearningQualityAgent()
    grant = _make_grant()
    res = _make_valid_specialist_result("LEARN-ATTRIBUTION")

    bundle = {
        "specialist_results": [res],
        "methodological_conflicts": ["meta_channel_lift_vs_attribution"],
    }
    qa_result = await agent.run(grant, bundle)

    assert qa_result.decision == QADecision.REVISE
    assert any("UNRECONCILED_METHODOLOGICAL_CONFLICT" in code for code in qa_result.issue_codes)
    assert len(qa_result.remediation_requests) > 0
    assert not qa_result.accepted_claim_ids


# --- 7. Parent Synthesis Tamper Detection ---

@pytest.mark.asyncio
async def test_parent_synthesis_tamper_detection() -> None:
    agent = LearningQualityAgent()
    grant = _make_grant()
    res = _make_valid_specialist_result("LEARN-ATTRIBUTION")

    bundle = {"specialist_results": [res]}
    qa_result = await agent.run(grant, bundle)
    assert qa_result.decision == QADecision.PASS

    # 1. Valid synthesis via LearningPerformanceAgent
    candidate = LearningPerformanceAgent.synthesize_learning_delta_candidate(
        qa_result,
        tenant_id="tenant-gamma",
    )
    assert candidate is not None
    assert agent.validate_parent_synthesis(qa_result, candidate) is True

    # 2. Tampered candidate with injected unauthorized claim must fail
    tampered_claims = candidate.model_copy(update={"accepted_claim_ids": ["est-learn-attribution-1", "unauthorized-injected-claim"]})
    with pytest.raises(ValueError, match="injected unauthorized claim"):
        agent.validate_parent_synthesis(qa_result, tampered_claims)

    # 3. Tampered digest must fail
    tampered_digest = candidate.model_copy(update={"qa_digest": "tampered_digest_hash_000000000000000000000000000000000000000000000000"})
    with pytest.raises(ValueError, match="does not match QA evidence bundle digest"):
        agent.validate_parent_synthesis(qa_result, tampered_digest)
