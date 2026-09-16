"""Focused unit and integration tests for Task DE-05: Provenance & Audit Layer (W_DEV).

Validates:
1. Normalized DevelopmentProvEvent schema, deterministic canonical serialization, and event hashing.
2. Authoritative backend control-plane Ed25519 signing and verification (zero sandbox trust).
3. Append-only persistence, per-tenant unbroken hash-chaining, and idempotency.
4. Complete W3C PROV graph (Entity, Activity, Agent, used, wasGeneratedBy, wasDerivedFrom, wasAssociatedWith, actedOnBehalfOf).
5. Output candidate content digest tracking and derivation linkage (wasDerivedFrom) across attempts.
6. Sensitive prompt/context privacy: SHA-256 digest, classification, vault reference, and credential redaction.
7. SLSA v1.0 / in-toto attestation generation for release deliverables.
8. AuditLineageValidator verification of development engine lineage, integrity, and tamper detection.
9. Fail-closed state machine transition guards enforcing valid provenance recording.
10. TaskStateService integration for checkpoints, HITL approval decision binding, and lineage reconstruction.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
import uuid
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.core.exceptions import PolicyViolationError
from app.orchestration.development_state_machine import DevelopmentStateMachine
from app.schemas.development.approval_token import DevelopmentApprovalToken
from app.schemas.development.provenance import (
    DevelopmentProvEvent,
    InTotoStatement,
    canonical_development_event_bytes,
)
from app.schemas.provenance import AuditLineageStage
from app.schemas.task_state import (
    CanonicalTaskState,
    DevelopmentExecutionLease,
    DevelopmentWorkflowCheckpoint,
    DevelopmentWorkflowState,
    TaskStatus,
)
from app.security.authorization_boundary import CallerIdentity
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.audit_validator import AuditLineageValidator
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository


class FakeTaskStateRepo:
    """In-memory stand-in for task state repository."""

    def __init__(self) -> None:
        self._states: dict[str, CanonicalTaskState] = {}

    async def get(self, tenant_id: str, task_id: str) -> CanonicalTaskState | None:
        return self._states.get(f"{tenant_id}:{task_id}")

    async def save(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self._states[f"{tenant_id}:{state.task_id}"] = state

    async def list_all(self, tenant_id: str) -> list[CanonicalTaskState]:
        return [s for k, s in self._states.items() if k.startswith(f"{tenant_id}:")]


# ===========================================================================
# 1. Schema, Canonical Serialization & Hashing Tests
# ===========================================================================

def test_canonical_development_event_bytes_deterministic() -> None:
    """Canonical serialization produces byte-for-byte identical output regardless of field dict order."""
    now = datetime(2026, 9, 16, 12, 0, 0, tzinfo=UTC)
    event1 = DevelopmentProvEvent(
        event_id="pe-dev-001",
        task_id="task-dev-01",
        workflow_id="wf-01",
        step_id="step-1",
        attempt_id="att-1",
        tenant_id="tenant-alpha",
        work_region="us-east-1",
        agent_id="W_DEV",
        worker_role="W_DEV",
        activity_id="subagent_execution",
        input_snapshot_hash="a" * 64,
        output_snapshot_hash="b" * 64,
        trace_id="tr-fixed-01",
        occurred_at=now,
    )
    event2 = DevelopmentProvEvent(
        output_snapshot_hash="b" * 64,
        input_snapshot_hash="a" * 64,
        activity_id="subagent_execution",
        worker_role="W_DEV",
        agent_id="W_DEV",
        work_region="us-east-1",
        tenant_id="tenant-alpha",
        attempt_id="att-1",
        step_id="step-1",
        workflow_id="wf-01",
        task_id="task-dev-01",
        event_id="pe-dev-001",
        trace_id="tr-fixed-01",
        occurred_at=now,
    )

    b1 = canonical_development_event_bytes(event1)
    b2 = canonical_development_event_bytes(event2)
    assert b1 == b2
    assert isinstance(b1, bytes)
    parsed = json.loads(b1.decode("utf-8"))
    assert parsed["event_id"] == "pe-dev-001"
    assert parsed["task_id"] == "task-dev-01"


def test_event_hash_chaining() -> None:
    """Event hash computation incorporates previous_event_hash and canonical bytes."""
    now = datetime(2026, 9, 16, 12, 0, 0, tzinfo=UTC)
    ev1 = DevelopmentProvEvent(
        event_id="pe-1",
        task_id="task-1",
        workflow_id="wf-1",
        step_id="step-1",
        attempt_id="att-1",
        activity_id="init",
        input_snapshot_hash="0" * 64,
        occurred_at=now,
    )
    h1 = ev1.compute_event_hash(prev_hash=None)
    assert len(h1) == 64

    ev2 = DevelopmentProvEvent(
        event_id="pe-2",
        task_id="task-1",
        workflow_id="wf-1",
        step_id="step-1",
        attempt_id="att-1",
        activity_id="step2",
        input_snapshot_hash="0" * 64,
        previous_event_hash=h1,
        occurred_at=now,
    )
    h2 = ev2.compute_event_hash(prev_hash=h1)
    assert h2 != h1
    assert len(h2) == 64


# ===========================================================================
# 2. Control Plane Cryptographic Signing & Verification Tests
# ===========================================================================

def test_control_plane_signature_verification() -> None:
    """Ed25519 signature generated over canonical bytes verifies successfully and rejects tampering."""
    private_key = Ed25519PrivateKey.generate()
    pub_pem = private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    event = DevelopmentProvEvent(
        event_id="pe-sig-01",
        task_id="task-dev-01",
        workflow_id="wf-01",
        step_id="step-1",
        attempt_id="att-1",
        activity_id="deliverable_sealed",
        input_snapshot_hash="1" * 64,
        output_snapshot_hash="2" * 64,
    )

    sig = sign_payload(event.canonical_bytes(), private_key)
    signed_event = event.model_copy(update={"control_plane_signature": sig})

    # Verification succeeds with correct public key
    assert signed_event.verify_signature(public_key_pem=pub_pem) is True

    # Verification fails if payload is tampered
    tampered_event = signed_event.model_copy(update={"output_snapshot_hash": "3" * 64})
    assert tampered_event.verify_signature(public_key_pem=pub_pem) is False

    # Verification fails with different public key
    other_key = Ed25519PrivateKey.generate()
    other_pem = other_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    assert signed_event.verify_signature(public_key_pem=other_pem) is False


# ===========================================================================
# 3. ProvenanceRecorder Development Event Recording & Chaining Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_record_development_event_append_and_chain() -> None:
    """ProvenanceRecorder captures, signs, and hash-chains development events in tenant ledger."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    # 1. Record planning event
    ev1 = await recorder.record_development_event(
        tenant_id="tenant-acme",
        task_id="task-101",
        workflow_id="wf-101",
        step_id="spec_review",
        attempt_id="att-1",
        activity_type="development_planning",
        agent_id="W_DEV",
        input_snapshot_hash="input-hash-1",
        output_snapshot_hash="output-hash-1",
    )
    assert ev1.event_id.startswith("pe-dev-")
    assert ev1.previous_event_hash is None
    assert ev1.control_plane_signature is not None
    assert ev1.verify_signature(public_key_pem=recorder.control_plane_public_key_pem) is True

    # 2. Record subagent sealed output event
    ev2 = await recorder.record_development_event(
        tenant_id="tenant-acme",
        task_id="task-101",
        workflow_id="wf-101",
        step_id="spec_review",
        attempt_id="att-1",
        activity_type="development_result_sealed",
        agent_id="subagent-spec",
        worker_role="spec_author",
        input_snapshot_hash="input-hash-1",
        output_snapshot_hash="output-hash-2",
        artifact_hashes={"spec.md": "sha256-spec-hash"},
    )
    assert ev2.previous_event_hash is not None
    assert ev2.control_plane_signature is not None
    assert ev2.verify_signature(public_key_pem=recorder.control_plane_public_key_pem) is True

    # 3. Verify underlying repository chain
    chain = await repo.chain("tenant-acme")
    assert len(chain) == 2
    assert repo.verify(chain) is True
    assert chain[1].prev_record_hash == chain[0].record_hash


@pytest.mark.asyncio
async def test_record_development_event_idempotency() -> None:
    """Duplicate append with same event_id is idempotent."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    stable_id = "pe-stable-001"
    ev1 = await recorder.record_development_event(
        tenant_id="tenant-acme",
        task_id="task-101",
        workflow_id="wf-101",
        step_id="step-1",
        attempt_id="att-1",
        activity_type="test_event",
        input_snapshot_hash="0" * 32,
        event_id=stable_id,
    )
    ev2 = await recorder.record_development_event(
        tenant_id="tenant-acme",
        task_id="task-101",
        workflow_id="wf-101",
        step_id="step-1",
        attempt_id="att-1",
        activity_type="test_event",
        input_snapshot_hash="0" * 32,
        event_id=stable_id,
    )

    assert ev1.event_id == ev2.event_id
    chain = await repo.chain("tenant-acme")
    assert len(chain) == 1


# ===========================================================================
# 4. W3C PROV Graph Construction & Relations Tests
# ===========================================================================

def test_build_development_w3c_prov_graph() -> None:
    """W3C PROV graph contains complete activities, agents, entities, and directed relations."""
    recorder = ProvenanceRecorder(FakeProvenanceRepository())

    bundle = recorder.build_development_w3c_prov(
        tenant_id="tenant-xyz",
        task_id="task-42",
        workflow_id="wf-42",
        step_id="code_gen",
        attempt_id="att-1",
        activity_type="development_result_sealed",
        agent_id="subagent_coder",
        worker_role="coder",
        input_snapshot_hash="input-sha-abc",
        output_snapshot_hash="output-sha-def",
        artifact_hashes={"main.py": "py-hash-1", "test_main.py": "py-hash-2"},
        sandbox_id="sbx-isolated-42",
        reviewer_id="rev-alice",
        approval_token_id="tok-approved-99",
    )

    # 1. Activities
    act_ids = {a.id for a in bundle.activities}
    assert any(":activity:development:task-42:code_gen:att-1:" in aid for aid in act_ids)

    # 2. Agents
    ag_ids = {ag.id for ag in bundle.agents}
    assert "urn:enterprise_os:agent:orchestrator:tenant-xyz" in ag_ids
    assert "urn:enterprise_os:agent:worker:W_DEV" in ag_ids
    assert "urn:enterprise_os:agent:subagent:subagent_coder" in ag_ids
    assert "urn:enterprise_os:agent:sandbox_controller:sbx-isolated-42" in ag_ids
    assert "urn:enterprise_os:agent:human_reviewer:rev-alice" in ag_ids

    # 3. Entities
    ent_ids = {e.id for e in bundle.entities}
    assert "urn:enterprise_os:entity:task_grant:task-42:code_gen" in ent_ids
    assert "urn:enterprise_os:entity:input_snapshot:input-sha-abc" in ent_ids
    assert any(":entity:candidate:code_gen:att-1:" in eid for eid in ent_ids)
    assert any(":entity:artifact:py-hash-1" in eid for eid in ent_ids)
    assert "urn:enterprise_os:entity:approval_token:tok-approved-99" in ent_ids

    # 4. Relations
    rel_types = [r.relation_type.value for r in bundle.relations]
    assert "prov:wasAssociatedWith" in rel_types
    assert "prov:actedOnBehalfOf" in rel_types
    assert "prov:used" in rel_types
    assert "prov:wasGeneratedBy" in rel_types
    assert "prov:wasDerivedFrom" in rel_types

    # Verify candidate was derived from input snapshot
    candidate_urn = [e.id for e in bundle.entities if ":entity:candidate:" in e.id][0]
    input_urn = "urn:enterprise_os:entity:input_snapshot:input-sha-abc"
    derivation_rels = [
        r for r in bundle.relations
        if r.relation_type.value == "prov:wasDerivedFrom"
        and r.source_id == candidate_urn
        and r.target_id == input_urn
    ]
    assert len(derivation_rels) == 1


def test_retry_candidate_derivation_from_prior_attempt() -> None:
    """Retry candidate links to predecessor candidate via prov:wasDerivedFrom."""
    recorder = ProvenanceRecorder(FakeProvenanceRepository())

    bundle = recorder.build_development_w3c_prov(
        tenant_id="tenant-xyz",
        task_id="task-42",
        workflow_id="wf-42",
        step_id="code_gen",
        attempt_id="att-2",
        activity_type="development_result_sealed",
        agent_id="subagent_coder",
        input_snapshot_hash="input-sha-abc",
        output_snapshot_hash="output-sha-def-2",
        derived_from_attempt_id="att-1",
        derived_from_output_hash="output-sha-def-1",
    )

    cand_urn = [e.id for e in bundle.entities if ":entity:candidate:code_gen:att-2:" in e.id][0]
    prior_cand_urn = "urn:enterprise_os:entity:candidate:code_gen:att-1:output-sha-def-1"

    prior_derivations = [
        r for r in bundle.relations
        if r.relation_type.value == "prov:wasDerivedFrom"
        and r.source_id == cand_urn
        and r.target_id == prior_cand_urn
    ]
    assert len(prior_derivations) == 1


# ===========================================================================
# 5. Sensitive Prompt Redaction & Privacy Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_prompt_privacy_redaction_and_vault_reference() -> None:
    """Raw sensitive prompt is never stored plaintext; hashed, vaulted, and credentials redacted."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    raw_secret_prompt = "Refactor payment handler using secret_key='sk_live_998877665544332211'"
    expected_prompt_hash = hashlib.sha256(raw_secret_prompt.encode("utf-8")).hexdigest()

    event = await recorder.record_development_event(
        tenant_id="tenant-privacy",
        task_id="task-sec-1",
        workflow_id="wf-sec",
        step_id="payments",
        attempt_id="att-1",
        activity_type="code_implementation",
        input_snapshot_hash="in-hash",
        raw_prompt=raw_secret_prompt,
        metadata={"Authorization": "Bearer 112233445566778899", "env": "prod"},
    )

    # Event itself stores vault reference, not plaintext
    assert raw_secret_prompt not in str(event.model_dump())
    assert event.evidence_ref is not None
    assert "vault://prompts/task-sec-1/payments/att-1/" in event.evidence_ref

    # Metadata stores prompt hash and redacted secrets
    assert event.metadata["prompt_hash"] == expected_prompt_hash
    assert event.metadata["prompt_classification"] == "CONFIDENTIAL"
    assert "112233445566778899" not in str(event.metadata)
    assert "[REDACTED]" in event.metadata["Authorization"]

    # Underlying ledger document does not contain raw secrets
    chain = await repo.chain("tenant-privacy")
    doc_str = json.dumps(chain[0].model_dump(mode="json"))
    assert raw_secret_prompt not in doc_str
    assert "112233445566778899" not in doc_str


# ===========================================================================
# 6. SLSA v1.0 / In-Toto Attestation Generation Tests
# ===========================================================================

def test_slsa_v1_in_toto_attestation_generation() -> None:
    """SLSA v1.0 attestation predicate and in-toto statement generated for release deliverables."""
    recorder = ProvenanceRecorder(FakeProvenanceRepository())

    artifacts = {
        "dist/app-v1.tar.gz": "sha256-dist-tar-gz-hash",
        "dist/checksums.txt": "sha256-checksums-hash",
    }
    dependencies = [
        {"name": "python", "digest": {"version": "3.12.0"}, "annotations": {"vendor": "cpython"}},
        {"name": "enterprise_os/sandbox", "digest": {"gitCommit": "abcdef123456"}},
    ]

    statement = recorder.generate_slsa_attestation(
        task_id="task-release-01",
        step_id="build_and_package",
        attempt_id="att-1",
        builder_id="urn:enterprise_os:builder:W_DEV:v1",
        artifacts=artifacts,
        resolved_dependencies=dependencies,
        build_config={"optimization": "release", "strict_provenance": True},
    )

    assert isinstance(statement, InTotoStatement)
    assert statement._type == "https://in-toto.io/Statement/v1"
    assert statement.predicateType == "https://slsa.dev/provenance/v1"

    # Verify subject descriptors
    subj_names = {s.name for s in statement.subject}
    assert "dist/app-v1.tar.gz" in subj_names
    assert statement.subject[0].digest.get("sha256") is not None

    # Verify build definition
    predicate = statement.predicate
    assert predicate.buildDefinition.buildType == "https://enterprise_os.dev/attestations/development_engine/v1"
    assert predicate.buildDefinition.externalParameters["task_id"] == "task-release-01"
    assert len(predicate.buildDefinition.resolvedDependencies) == 2

    # Verify run details
    assert predicate.runDetails.builder.id == "urn:enterprise_os:builder:W_DEV:v1"
    assert predicate.runDetails.metadata["step_id"] == "build_and_package"


# ===========================================================================
# 7. AuditLineageValidator Lineage & Integrity Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_audit_validator_development_lineage_success() -> None:
    """AuditLineageValidator verifies complete, uncorrupted W_DEV audit trail."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    task_id = "task-dev-audit-1"
    await recorder.record_development_event(
        tenant_id="tenant-audit",
        task_id=task_id,
        workflow_id="wf-audit",
        step_id="step-1",
        attempt_id="att-1",
        activity_type="development_planning",
        input_snapshot_hash="in-1",
        output_snapshot_hash="out-1",
    )
    await recorder.record_development_event(
        tenant_id="tenant-audit",
        task_id=task_id,
        workflow_id="wf-audit",
        step_id="step-1",
        attempt_id="att-1",
        activity_type="development_result_sealed",
        input_snapshot_hash="in-1",
        output_snapshot_hash="out-2",
        artifact_hashes={"bundle.js": "js-hash-1"},
    )

    validator = AuditLineageValidator(
        provenance_repository=repo,
        provenance_recorder=recorder,
        crypto_validator=CryptographicValidator(public_key_pem=recorder.control_plane_public_key_pem),
    )

    report = await validator.validate_development_lineage(
        tenant_id="tenant-audit",
        task_id=task_id,
        expected_deliverable_hash="out-2",
    )

    assert report.is_valid is True
    assert report.hash_chain_verified is True
    assert report.signatures_verified is True
    assert report.prov_graph_valid is True
    assert AuditLineageStage.DEVELOPMENT_ENGINE.value in report.stages_verified
    assert len(report.detected_gaps) == 0


@pytest.mark.asyncio
async def test_audit_validator_detects_tampered_signature() -> None:
    """AuditLineageValidator flags tampered control-plane signature as invalid."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    task_id = "task-dev-tampered"
    await recorder.record_development_event(
        tenant_id="tenant-tamper",
        task_id=task_id,
        workflow_id="wf-tamper",
        step_id="step-1",
        attempt_id="att-1",
        activity_type="development_result_sealed",
        input_snapshot_hash="in-1",
        output_snapshot_hash="out-1",
    )

    # Tamper with the signature in the ledger
    chain = await repo.chain("tenant-tamper")
    record = chain[0]
    dev_ev = dict(record.metadata["development_prov_event"])
    dev_ev["control_plane_signature"] = "aW52YWxpZHNpZ25hdHVyZQ=="  # base64 invalid signature
    record.metadata["development_prov_event"] = dev_ev

    validator = AuditLineageValidator(
        provenance_repository=repo,
        provenance_recorder=recorder,
        crypto_validator=CryptographicValidator(public_key_pem=recorder.control_plane_public_key_pem),
    )

    report = await validator.validate_development_lineage(
        tenant_id="tenant-tamper",
        task_id=task_id,
    )

    assert report.is_valid is False
    assert report.signatures_verified is False
    assert any("INVALID_SIGNATURE" == f.status for f in report.findings)


# ===========================================================================
# 8. State Machine Fail-Closed Transition Guards Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_state_machine_transition_with_provenance_success() -> None:
    """transition_with_provenance advances state machine and records signed audit event."""
    sm = DevelopmentStateMachine()
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    # Transition RECEIVED -> POLICY_BOUND
    cp = await sm.transition_with_provenance(
        current_state=DevelopmentWorkflowState.RECEIVED,
        target_state=DevelopmentWorkflowState.POLICY_BOUND,
        task_id="task-sm-prov-1",
        workflow_id="wf-sm-1",
        step_id="step-init",
        attempt_id="att-1",
        idempotency_key="key-001",
        provenance_recorder=recorder,
        tenant_id="tenant-sm",
        input_snapshot_hash="in-hash-01",
    )

    assert cp.state == DevelopmentWorkflowState.POLICY_BOUND
    assert cp.state_data.get("provenance_verified") is True
    assert cp.state_data.get("provenance_event_hash") is not None
    assert cp.state_data.get("provenance_signature") is not None

    chain = await repo.chain("tenant-sm")
    assert len(chain) == 1
    assert "development:transition_policy_bound" in chain[0].activity


@pytest.mark.asyncio
async def test_state_machine_fail_closed_guard_blocks_corrupted_provenance() -> None:
    """State machine transition guards fail closed when provenance recording fails or is unverified."""
    sm = DevelopmentStateMachine()

    # 1. Guard blocks transition when provenance recording failed
    with pytest.raises(PolicyViolationError, match="Provenance recording failed"):
        sm.validate_transition_guards(
            current_state=DevelopmentWorkflowState.RECEIVED,
            target_state=DevelopmentWorkflowState.POLICY_BOUND,
            step_id="step-1",
            attempt_id="att-1",
            state_data={"provenance_recording_failed": True},
        )

    # 2. Guard blocks transition to NEXT_STEP when provenance_verified is False
    with pytest.raises(PolicyViolationError, match="Provenance verification failed"):
        sm.validate_transition_guards(
            current_state=DevelopmentWorkflowState.APPROVED,
            target_state=DevelopmentWorkflowState.NEXT_STEP,
            step_id="step-1",
            attempt_id="att-1",
            state_data={"provenance_verified": False},
        )


# ===========================================================================
# 9. TaskStateService Integration & Lineage Reconstruction Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_task_state_service_checkpoint_provenance_integration() -> None:
    """TaskStateService invokes record_development_event during save_development_checkpoint."""
    task_repo = FakeTaskStateRepo()
    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(prov_repo)
    service = TaskStateService(task_repo, provenance_recorder=recorder)

    checkpoint = DevelopmentWorkflowCheckpoint(
        task_id="task-tss-prov-1",
        workflow_id="wf-tss-1",
        step_id="step-1",
        attempt_id="att-1",
        state=DevelopmentWorkflowState.SANDBOX_PROVISIONING,
        idempotency_key="cp-key-01",
        state_data={"input_snapshot_hash": "in-hash-99", "candidate_hash": "out-hash-99"},
    )

    saved = await service.save_development_checkpoint("tenant-tss", checkpoint)
    assert saved.state == DevelopmentWorkflowState.SANDBOX_PROVISIONING

    chain = await prov_repo.chain("tenant-tss")
    assert len(chain) == 1
    rec = chain[0]
    assert rec.metadata.get("task_id") == "task-tss-prov-1"
    assert rec.metadata.get("development_prov_event") is not None
    dev_ev = DevelopmentProvEvent.model_validate(rec.metadata["development_prov_event"])
    assert dev_ev.input_snapshot_hash == "in-hash-99"
    assert dev_ev.output_snapshot_hash == "out-hash-99"


@pytest.mark.asyncio
async def test_reconstruct_development_lineage() -> None:
    """ProvenanceRecorder reconstructs end-to-end task history with verified signatures."""
    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(prov_repo)

    task_id = "task-recon-01"
    await recorder.record_development_event(
        tenant_id="tenant-recon",
        task_id=task_id,
        workflow_id="wf-recon",
        step_id="step-1",
        attempt_id="att-1",
        activity_type="init",
        input_snapshot_hash="in-01",
    )
    await recorder.record_development_event(
        tenant_id="tenant-recon",
        task_id=task_id,
        workflow_id="wf-recon",
        step_id="step-1",
        attempt_id="att-1",
        activity_type="seal",
        input_snapshot_hash="in-01",
        output_snapshot_hash="out-01",
        artifact_hashes={"app.py": "hash-app"},
    )

    lineage = await recorder.reconstruct_development_lineage(
        tenant_id="tenant-recon",
        task_id=task_id,
    )

    assert lineage["found"] is True
    assert lineage["event_count"] == 2
    assert lineage["signatures_verified"] is True
    assert lineage["development_chain_verified"] is True
    assert lineage["repository_chain_verified"] is True
    assert "app.py" in lineage["artifacts"]
    assert len(lineage["w3c_prov_bundles"]) == 2
