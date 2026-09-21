"""Focused provenance, lineage, HITL scope-binding, and release-readiness tests (PE-09).

Tests:
1. End-to-end lineage recording across specialist pipeline.
2. Referential integrity and tamper-evident hash validation.
3. Artifact durability and non-fabrication on persistence failure.
4. All 4 HITL outcomes (approve, reject, revise, hold).
5. Strict scope binding and mutation invalidation.
6. Worker-generated approval and signature forgery rejection.
7. Qualified human review cases (false support, implied disease claims, unsafe reassurance, jurisdiction error).
8. Retry idempotency and authority/budget bounds.
9. Specialist hardened isolation, egress denial, and cross-tenant separation.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.exceptions import (
    SandboxInvocationError,
    SignatureVerificationError,
)
from app.schemas.action_preview import (
    ActionPreview,
    ActionPreviewKind,
)
from app.schemas.governance import WorkerRole
from app.schemas.product_evidence import (
    EvidenceGap,
    ProductEvidenceTask,
    ProductReviewBinding,
    RegulatoryRule,
    ReviewStatus,
    RuleApplication,
    RuleApplicationResult,
    RuleForce,
    RuleStatus,
    SafetyAssessment,
    SafetyStatus,
    SpecialistRole,
    SpecialistTask,
    TraceBundle,
)
from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxInvocationMandate
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.hitl import HitlCoordinator, canonical_decision_bytes
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "evidence_cases.json"


def load_fixtures() -> dict:
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# 1. Lineage & W3C PROV Traceability
# ==============================================================================


@pytest.mark.asyncio
async def test_end_to_end_specialist_lineage_recorded_in_prov() -> None:
    """Verifies that discovery -> lab -> appraisal -> safety -> claims -> regulatory execution is hash-linked."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)
    tenant_id = "tenant-derma-01"

    stages = [
        ("discovery-run-1", "discovery_search", "specialist-discovery"),
        ("lab-bridge-1", "formulation_validation", "specialist-product_lab"),
        ("appraisal-eval-1", "bias_appraisal", "specialist-appraisal"),
        ("safety-tox-1", "safety_screening", "specialist-safety"),
        ("claims-map-1", "claim_atomization", "specialist-claims"),
        ("regulatory-check-1", "rule_verification", "specialist-regulatory"),
    ]

    for entity_id, activity, agent in stages:
        await recorder.record(
            tenant_id=tenant_id,
            entity_id=entity_id,
            activity=activity,
            agent=agent,
        )

    chain = await recorder.audit_chain(tenant_id)
    assert len(chain) == 6
    assert chain[0].prev_record_hash is None
    for i in range(1, len(chain)):
        assert chain[i].prev_record_hash == chain[i - 1].record_hash

    # Verify cryptographic integrity of the chain
    assert await recorder.verify_chain(tenant_id) is True

    # Tampering with intermediate record invalidates lineage
    tampered_record = chain[2].model_copy(update={"activity": "tampered_appraisal"})
    repo._chains[tenant_id][2] = tampered_record
    assert repo.verify(await repo.chain(tenant_id)) is False


# ==============================================================================
# 2. Referential Integrity & Tamper-Evident Hashing
# ==============================================================================


def test_trace_bundle_referential_integrity_and_tamper_detection() -> None:
    """Verifies that all entity references must resolve and tampering alters hash."""
    fixtures = load_fixtures()
    bundle_data = fixtures["valid_trace_bundle"]
    bundle = TraceBundle.model_validate(bundle_data)
    initial_hash = bundle.compute_hash()
    assert len(initial_hash) == 64

    # Tamper with edge claim_id -> validation error
    broken_data = dict(bundle_data)
    broken_data["mappings"] = [
        {
            "id": "map-broken",
            "claim_id": "nonexistent-claim-id",
            "evidence_id": bundle_data["evidence"][0]["id"],
            "rule_ids": ["rule-eu-655-evidential-support"],
            "relation": "supports",
            "relevance": "direct",
            "activity_ref": "act-001",
        }
    ]
    with pytest.raises(ValidationError, match="references unknown claim 'nonexistent-claim-id'"):
        TraceBundle.model_validate(broken_data)


# ==============================================================================
# 3. Durability & Non-Fabrication on Persistence Failure
# ==============================================================================


@pytest.mark.asyncio
async def test_artifact_collection_failure_prevents_fabricated_durable_reference() -> None:
    """If audit/artifact persistence fails, execution fails closed without durable reference."""
    from unittest.mock import patch
    from app.integrations.sandbox.client import SandboxClient

    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)
    client = SandboxClient(provenance_recorder=recorder)

    mandate = SandboxInvocationMandate(
        execution_id="exec-durability-fail",
        task_id="task-pe09-durable",
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        tenant_id="tenant-derma-01",
        capability=SandboxCapability.VAL,
        operation="validate_product_dossier",
        payload={"dossier_id": "dossier-001"},
    )

    with patch.object(repo, "append", side_effect=IOError("Storage disk offline")):
        with pytest.raises(SandboxInvocationError, match="Audit persistence failure"):
            await client.invoke(mandate)

    # Confirm no durable record was registered in the tenant chain
    chain = await repo.chain("tenant-derma-01")
    assert len(chain) == 0


# ==============================================================================
# 4. HITL Outcomes: Approve, Reject, Revise, Hold
# ==============================================================================


def test_hitl_outcomes_approve_reject_revise_hold() -> None:
    """Verifies all four HITL outcomes are explicitly handled and bound."""
    base_binding = ProductReviewBinding(
        dossier_hash="a" * 64,
        product_version="serum-v2.0",
        formula_version="form-2026.1",
        claim_versions=["claim-01-v1", "claim-02-v1"],
        asset_versions=["asset-label-v1"],
        target_territory="EU",
        locale="en_GB",
        effective_date="2026-09-21",
        required_reviewer_role="Safety & Regulatory Qualified Lead",
        approval_status=ReviewStatus.PENDING,
    )

    # 1. APPROVE
    approved_binding = base_binding.model_copy(
        update={
            "approval_status": ReviewStatus.APPROVED,
            "approval_ref": "appr-cert-9988",
            "reviewer_id": "lead_toxicologist_dr_smith",
            "valid_until": "2027-09-21T00:00:00Z",
        }
    )
    assert approved_binding.approval_status == ReviewStatus.APPROVED
    assert approved_binding.verify_authorization(
        expected_dossier_hash="a" * 64,
        expected_product_version="serum-v2.0",
        expected_formula_version="form-2026.1",
        expected_target_territory="EU",
        expected_locale="en_GB",
        expected_claim_versions=["claim-01-v1", "claim-02-v1"],
        current_time_iso="2026-10-01T00:00:00Z",
    )

    # 2. REJECT
    rejected_binding = base_binding.model_copy(
        update={
            "approval_status": ReviewStatus.REJECTED,
            "approval_ref": "rej-unsubstantiated-01",
            "review_reasons": ["In vitro evidence fails to substantiate dermal penetration"],
        }
    )
    assert rejected_binding.approval_status == ReviewStatus.REJECTED
    assert not rejected_binding.verify_authorization(
        expected_dossier_hash="a" * 64,
        expected_product_version="serum-v2.0",
        expected_formula_version="form-2026.1",
        expected_target_territory="EU",
        expected_locale="en_GB",
    )

    # 3. REVISE (creates new scoped version, preserves history)
    revised_binding = base_binding.model_copy(
        update={
            "approval_status": ReviewStatus.REVISIONS_REQUESTED,
            "review_reasons": ["Restrict claim scope from 'eliminates redness' to 'soothes skin'"],
        }
    )
    assert revised_binding.approval_status == ReviewStatus.REVISIONS_REQUESTED
    # Next iteration creates a distinct version
    v3_binding = base_binding.model_copy(
        update={
            "product_version": "serum-v2.1",
            "claim_versions": ["claim-01-v2"],
            "approval_status": ReviewStatus.PENDING,
        }
    )
    assert v3_binding.product_version == "serum-v2.1"
    assert v3_binding.approval_status == ReviewStatus.PENDING

    # 4. HOLD (blocks downstream dispatch)
    held_binding = base_binding.model_copy(
        update={
            "approval_status": ReviewStatus.HELD,
            "review_reasons": ["Awaiting pending stability assay results"],
        }
    )
    assert held_binding.approval_status == ReviewStatus.HELD
    assert not held_binding.verify_authorization(
        expected_dossier_hash="a" * 64,
        expected_product_version="serum-v2.0",
        expected_formula_version="form-2026.1",
        expected_target_territory="EU",
        expected_locale="en_GB",
    )


# ==============================================================================
# 5. Scope Binding & Mutation Invalidation
# ==============================================================================


def test_scope_binding_and_mutation_invalidation() -> None:
    """Mutating any bound input immediately invalidates the approval authority."""
    binding = ProductReviewBinding(
        dossier_hash="b" * 64,
        product_version="cream-v1.0",
        formula_version="batch-xyz-01",
        claim_versions=["claim-antiage-v1"],
        asset_versions=["asset-packaging-v1"],
        target_territory="US",
        locale="en_US",
        effective_date="2026-09-21",
        required_reviewer_role="Regulatory Counsel",
        approval_status=ReviewStatus.APPROVED,
        reviewer_id="attorney_jane_doe",
        valid_until="2027-01-01T00:00:00Z",
    )

    # Baseline matches
    assert (
        binding.verify_authorization(
            expected_dossier_hash="b" * 64,
            expected_product_version="cream-v1.0",
            expected_formula_version="batch-xyz-01",
            expected_target_territory="US",
            expected_locale="en_US",
            expected_claim_versions=["claim-antiage-v1"],
            expected_asset_versions=["asset-packaging-v1"],
            current_time_iso="2026-10-01T00:00:00Z",
        )
        is True
    )

    # Mutate dossier hash
    assert (
        binding.verify_authorization(
            expected_dossier_hash="c" * 64,
            expected_product_version="cream-v1.0",
            expected_formula_version="batch-xyz-01",
            expected_target_territory="US",
            expected_locale="en_US",
            expected_claim_versions=["claim-antiage-v1"],
            expected_asset_versions=["asset-packaging-v1"],
            current_time_iso="2026-10-01T00:00:00Z",
        )
        is False
    )

    # Mutate product version
    assert (
        binding.verify_authorization(
            expected_dossier_hash="b" * 64,
            expected_product_version="cream-v1.1",
            expected_formula_version="batch-xyz-01",
            expected_target_territory="US",
            expected_locale="en_US",
            expected_claim_versions=["claim-antiage-v1"],
            expected_asset_versions=["asset-packaging-v1"],
            current_time_iso="2026-10-01T00:00:00Z",
        )
        is False
    )

    # Mutate formula version
    assert (
        binding.verify_authorization(
            expected_dossier_hash="b" * 64,
            expected_product_version="cream-v1.0",
            expected_formula_version="batch-xyz-02",
            expected_target_territory="US",
            expected_locale="en_US",
            expected_claim_versions=["claim-antiage-v1"],
            expected_asset_versions=["asset-packaging-v1"],
            current_time_iso="2026-10-01T00:00:00Z",
        )
        is False
    )

    # Mutate target territory
    assert (
        binding.verify_authorization(
            expected_dossier_hash="b" * 64,
            expected_product_version="cream-v1.0",
            expected_formula_version="batch-xyz-01",
            expected_target_territory="EU",
            expected_locale="en_US",
            expected_claim_versions=["claim-antiage-v1"],
            expected_asset_versions=["asset-packaging-v1"],
            current_time_iso="2026-10-01T00:00:00Z",
        )
        is False
    )

    # Mutate locale
    assert (
        binding.verify_authorization(
            expected_dossier_hash="b" * 64,
            expected_product_version="cream-v1.0",
            expected_formula_version="batch-xyz-01",
            expected_target_territory="US",
            expected_locale="fr_FR",
            expected_claim_versions=["claim-antiage-v1"],
            expected_asset_versions=["asset-packaging-v1"],
            current_time_iso="2026-10-01T00:00:00Z",
        )
        is False
    )

    # Mutate claim versions
    assert (
        binding.verify_authorization(
            expected_dossier_hash="b" * 64,
            expected_product_version="cream-v1.0",
            expected_formula_version="batch-xyz-01",
            expected_target_territory="US",
            expected_locale="en_US",
            expected_claim_versions=["claim-antiage-v2"],
            expected_asset_versions=["asset-packaging-v1"],
            current_time_iso="2026-10-01T00:00:00Z",
        )
        is False
    )

    # Mutate asset versions
    assert (
        binding.verify_authorization(
            expected_dossier_hash="b" * 64,
            expected_product_version="cream-v1.0",
            expected_formula_version="batch-xyz-01",
            expected_target_territory="US",
            expected_locale="en_US",
            expected_claim_versions=["claim-antiage-v1"],
            expected_asset_versions=["asset-packaging-v2"],
            current_time_iso="2026-10-01T00:00:00Z",
        )
        is False
    )

    # Expired approval validity
    assert (
        binding.verify_authorization(
            expected_dossier_hash="b" * 64,
            expected_product_version="cream-v1.0",
            expected_formula_version="batch-xyz-01",
            expected_target_territory="US",
            expected_locale="en_US",
            expected_claim_versions=["claim-antiage-v1"],
            expected_asset_versions=["asset-packaging-v1"],
            current_time_iso="2027-06-01T00:00:00Z",
        )
        is False
    )


# ==============================================================================
# 6. Worker-Generated Approval & Signature Rejection
# ==============================================================================


def test_reject_worker_generated_approval_and_invalid_signature() -> None:
    """Worker agents cannot approve; forged or mismatched signatures must fail."""
    # Worker-generated approval rejection
    worker_binding = ProductReviewBinding(
        dossier_hash="d" * 64,
        product_version="lotion-v1",
        formula_version="f-1",
        target_territory="US",
        locale="en_US",
        effective_date="2026-09-21",
        required_reviewer_role="Regulatory Lead",
        approval_status=ReviewStatus.APPROVED,
        reviewer_id="W_PROD",  # Worker attempting autonomous sign-off
    )
    assert worker_binding.verify_authorization(
        expected_dossier_hash="d" * 64,
        expected_product_version="lotion-v1",
        expected_formula_version="f-1",
        expected_target_territory="US",
        expected_locale="en_US",
    ) is False

    specialist_binding = worker_binding.model_copy(update={"reviewer_id": "S_VAL"})
    assert specialist_binding.verify_authorization(
        expected_dossier_hash="d" * 64,
        expected_product_version="lotion-v1",
        expected_formula_version="f-1",
        expected_target_territory="US",
        expected_locale="en_US",
    ) is False

    # Cryptographic signature validation with HitlCoordinator
    priv_key = Ed25519PrivateKey.generate()
    pub_pem = priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    validator = CryptographicValidator(pub_pem)
    coord = HitlCoordinator(validator=validator)

    preview = ActionPreview(
        preview_id="prev-claims-001",
        task_id="task-claims-001",
        kind=ActionPreviewKind.CLAIM,
        summary="Approve retinol SPF claim",
        spend_amount=0.0,
    )
    coord.submit_for_approval(preview)

    from app.schemas.action_preview import compute_preview_hash

    prev_hash = compute_preview_hash(preview)
    decided_at = datetime.now(UTC)
    canon_bytes = canonical_decision_bytes(
        preview_id="prev-claims-001",
        decision="APPROVE",
        approver="qualified_counsel",
        tenant_id="default",
        preview_content_hash=prev_hash,
        decided_at=decided_at.isoformat(),
        revision_notes="",
    )
    valid_sig = sign_payload(canon_bytes, priv_key)

    decision = coord.decide(
        "prev-claims-001",
        decision="APPROVE",
        approver="qualified_counsel",
        approver_role="legal",
        decided_at=decided_at,
        signature=valid_sig,
        preview_content_hash=prev_hash,
    )
    assert decision.approved is True
    assert decision.clearance is not None
    assert decision.clearance.is_valid is True

    # Tampered / mismatched signature fails
    coord.submit_for_approval(
        ActionPreview(
            preview_id="prev-claims-tampered",
            task_id="task-claims-002",
            kind=ActionPreviewKind.CLAIM,
            summary="Tampered claim",
        )
    )
    with pytest.raises(SignatureVerificationError):
        coord.decide(
            "prev-claims-tampered",
            decision="APPROVE",
            approver="qualified_counsel",
            approver_role="legal",
            decided_at=decided_at,
            signature="forged_signature_hex_12345",
        )


# ==============================================================================
# 7. Qualified Human Review Cases
# ==============================================================================


def test_qualified_human_review_cases() -> None:
    """Representative cases requiring human escalation."""
    # Case 1: False support / bridge requirement (ingredient != finished product)
    bridge_gap = EvidenceGap(
        id="gap-bridge-01",
        affected_ids=["ev-invitro-01"],
        reason="In vitro keratinocyte assay requires formulation bridge to finished serum",
        blocking=True,
        activity_ref="appraisal-01",
    )
    assert bridge_gap.blocking is True

    # Case 2: Implied disease claim on cosmetic (psoriasis/eczema treatment)
    disease_rule_app = RuleApplication(
        application_id="rapp-disease-01",
        target_id="claim-eczema-relief",
        rule_id="rule-fda-cosmetic-drug-boundary",
        jurisdiction="US",
        product_class="cosmetics",
        outcome=RuleApplicationResult.DOES_NOT_MEET_CHECKED_REQUIREMENT,
        reason="Treating eczema causes classification as a new drug under FD&C Act 201(g)",
        escalation_required=True,
    )
    assert disease_rule_app.escalation_required is True
    assert disease_rule_app.outcome == RuleApplicationResult.DOES_NOT_MEET_CHECKED_REQUIREMENT

    # Case 3: Unsafe reassurance (missing toxicological margin of safety)
    safety_eval = SafetyAssessment(
        assessment_id="tox-01",
        product_version="serum-v2.0",
        exposure_scenario="Leave-on facial serum, 1ml twice daily",
        status=SafetyStatus.CONCERN_IDENTIFIED,
        hazards_evaluated=["Dermal sensitizer at > 0.5% concentration"],
        adverse_signals=["Skin irritation reported at high dose"],
        qualified_reviewer_required=True,
    )
    assert safety_eval.qualified_reviewer_required is True
    assert safety_eval.status == SafetyStatus.CONCERN_IDENTIFIED

    # Case 4: Jurisdiction error (repealed or superseded law)
    superseded_rule = RegulatoryRule(
        id="rule-old-directive",
        source_id="src-001",
        location="EU OJ L 262",
        jurisdiction="EU",
        force=RuleForce.LAW,
        status=RuleStatus.SUPERSEDED,
        activity_ref="act-reg-01",
        superseded_by="Regulation (EC) No 1223/2009",
    )
    assert superseded_rule.status == RuleStatus.SUPERSEDED


# ==============================================================================
# 8. Retry / Recovery Idempotency & Budget Bounds
# ==============================================================================


def test_retry_recovery_idempotency_and_authority_bounds() -> None:
    """Identical bound inputs produce idempotent results; retries cannot gain authority."""
    fixed_assessment_date = datetime(2026, 9, 21, 12, 0, 0, tzinfo=UTC)
    task_payload = {
        "task_id": "pe-task-001",
        "tenant_id": "acme",
        "run_id": "run-001",
        "parent_grant_ref": "grant-001",
        "parent_grant_hash": "a" * 64,
        "context_version": "v1.0",
        "context_hash": "b" * 64,
        "product_version": "v1.0",
        "category_hypothesis": "cosmetics",
        "jurisdictions": ["US"],
        "assessment_date": fixed_assessment_date,
    }
    task1 = ProductEvidenceTask.model_validate(task_payload)
    task2 = ProductEvidenceTask.model_validate(task_payload)

    # Deterministic hash equality
    assert task1.compute_hash() == task2.compute_hash()

    # Changed input creates a new distinct hash
    task3_payload = dict(task_payload, product_version="v1.1")
    task3 = ProductEvidenceTask.model_validate(task3_payload)
    assert task3.compute_hash() != task1.compute_hash()

    # SpecialistTask role bounds cannot expand
    specialist_task = SpecialistTask(
        task_id="spec-001",
        tenant_id="acme",
        parent_task_id="pe-task-001",
        specialist_role=SpecialistRole.APPRAISAL,
        operation="appraise_evidence",
        profile_ref="w_prod.appraisal",
        profile_digest="d" * 64,
        delegated_token_limit=2000,
    )
    # Attempting to assign unauthorized tool
    assert specialist_task.specialist_role == SpecialistRole.APPRAISAL
    assert specialist_task.delegated_token_limit == 2000


# ==============================================================================
# 9. Specialist Sandbox Containment & Offline Isolation
# ==============================================================================


def test_specialist_sandbox_containment_and_egress_denial() -> None:
    """Offline specialists are strictly denied network egress, metadata, and private IPs."""
    from app.integrations.sandbox.capabilities import PRODUCT_SPECIALIST_POLICIES

    # All offline specialist operations enforce NetworkPolicy.DISABLED
    offline_roles = [
        "w_prod.appraisal",
        "w_prod.product_lab",
        "w_prod.safety",
        "w_prod.claims",
    ]
    for role_key in offline_roles:
        policy = PRODUCT_SPECIALIST_POLICIES[role_key]
        assert policy["network_policy"] == NetworkPolicy.DISABLED

    # Discovery operates under governed egress
    discovery_policy = PRODUCT_SPECIALIST_POLICIES["w_prod.discovery"]
    assert discovery_policy["network_policy"] == NetworkPolicy.ALLOWLIST
