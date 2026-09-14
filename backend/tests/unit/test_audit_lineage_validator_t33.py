"""Unit and Integration Tests for Task-33 (T33): Validate End-to-End Audit Lineage & Integrity.

Validates:
1. Authoritative dependency verification on T30 (telemetry) and T31 (attribution/learning).
2. Model A boundary: no worker or specialist agent executes T33.
3. Cryptographic ledger integrity: hash chain continuity, record hashes, payload/metadata hashes, sequence ordering.
4. W3C PROV graph integrity: Entity-Activity-Agent relationships, relation resolution, tenant isolation.
5. Cryptographic signature verification: Ed25519 signatures on clearances and dispatches.
6. CTS state reconciliation: matching completed tasks and checkpoints to provenance records.
7. Explicit detection of gaps, missing dependencies, reordered records, and tampering.
8. Immutability guarantee: historical records are never mutated or resequenced.
9. Zero memory promotion (T32) and zero project closeout (T34).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.exceptions import PolicyViolationError
from app.persistence.repositories.provenance import (
    _compute_hash,
    _compute_metadata_hash,
)
from app.schemas.governance import RiskLevel, TenantScope, WorkerRole
from app.schemas.provenance import (
    AuditLineageStage,
    AuditValidationReport,
    ProvenanceRecord,
    ProvRelationType,
    W3CProvActivity,
    W3CProvAgent,
    W3CProvEntity,
    W3CProvRelation,
)
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.authorization_boundary import CallerIdentity
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.audit_validator import AuditLineageValidator
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository


class _FakeTaskStateRepository:
    """In-memory task state repository."""

    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task '{task_id}' not found.")
        return self.states[task_id]

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state


def _setup_t33_environment(
    tenant_id: str = "tenant-alpha",
    t30_status: TaskStatus = TaskStatus.COMPLETED,
    t30_approved: bool = True,
    has_t30: bool = True,
    t31_status: TaskStatus = TaskStatus.COMPLETED,
    t31_approved: bool = True,
    has_t31: bool = True,
) -> tuple[
    AuditLineageValidator,
    ProvenanceRecorder,
    FakeProvenanceRepository,
    dict[str, CanonicalTaskState],
    CallerIdentity,
    tuple[Ed25519PrivateKey, str],
]:
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)
    task_repo = _FakeTaskStateRepository()
    task_service = TaskStateService(task_repo, provenance_recorder=prov_recorder)

    # Generate Ed25519 keypair for cryptographic signature verification
    priv_key = Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    pub_pem = priv_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    crypto_validator = CryptographicValidator(public_key_pem=pub_pem)

    validator = AuditLineageValidator(
        provenance_repository=prov_repo,
        provenance_recorder=prov_recorder,
        task_state_service=task_service,
        crypto_validator=crypto_validator,
    )

    task_states: dict[str, CanonicalTaskState] = {}

    if has_t30:
        t30 = CanonicalTaskState(
            task_id="task-t30",
            directive_id="dir-t30",
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            status=t30_status,
            governance_approved=t30_approved,
            cts_state={"tenant_id": tenant_id, "telemetry_count": 25},
        )
        task_states["task-t30"] = t30
        task_repo.states["task-t30"] = t30

    if has_t31:
        t31 = CanonicalTaskState(
            task_id="task-t31",
            directive_id="dir-t31",
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            status=t31_status,
            governance_approved=t31_approved,
            cts_state={"tenant_id": tenant_id, "attribution_deliverable": {"status": "success"}},
        )
        task_states["task-t31"] = t31
        task_repo.states["task-t31"] = t31

    t33 = CanonicalTaskState(
        task_id="task-t33",
        directive_id="dir-t33",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.IN_PROGRESS,
        governance_approved=True,
        cts_state={"tenant_id": tenant_id},
    )
    task_states["task-t33"] = t33
    task_repo.states["task-t33"] = t33

    auditor_caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=TenantScope(tenant_id=tenant_id),
        risk_ceiling=RiskLevel.HIGH,
    )

    return validator, prov_recorder, prov_repo, task_states, auditor_caller, (priv_key, pub_pem)


async def _seed_full_pipeline_provenance(
    recorder: ProvenanceRecorder,
    tenant_id: str = "tenant-alpha",
) -> None:
    """Seed a complete valid end-to-end provenance chain for tenant."""
    # 1. Governance
    await recorder.record(
        tenant_id=tenant_id,
        entity_id="dir-001",
        activity="directive_accepted",
        agent="governance_controller",
        metadata={"directive_id": "dir-001", "intent": "launch_campaign"},
    )
    # 2. Orchestration
    await recorder.record(
        tenant_id=tenant_id,
        entity_id="grant-001",
        activity="task_granted",
        agent="intelligence_engine",
        metadata={"task_id": "task-w-dev-001", "worker_role": "W_DEV"},
    )
    # 3. RAG
    await recorder.record(
        tenant_id=tenant_id,
        entity_id="query:brand_voice",
        activity="mcp_data_vector_read",
        agent="intelligence_engine",
        metadata={"top_k": 5},
    )
    # 4. Sandbox Execution
    await recorder.record_sandbox_execution(
        tenant_id=tenant_id,
        task_id="task-w-dev-001",
        execution_id="exec-001",
        worker_role="W_DEV",
        capability="S_CODE",
        operation="generate_diff",
        lifecycle_stage="started",
        status="running",
    )
    await recorder.record_sandbox_execution(
        tenant_id=tenant_id,
        task_id="task-w-dev-001",
        execution_id="exec-001",
        worker_role="W_DEV",
        capability="S_CODE",
        operation="generate_diff",
        lifecycle_stage="completed",
        status="completed",
        output_summary={"files_modified": 2},
    )
    # 5. HITL Approval
    await recorder.record(
        tenant_id=tenant_id,
        entity_id="prev-001",
        activity="hitl_approved",
        agent="human_reviewer",
        metadata={"decision": "APPROVED", "approver": "lead_marketer"},
    )
    # 6. Actuation Dispatch
    await recorder.record(
        tenant_id=tenant_id,
        entity_id="dispatch-001",
        activity="actuation_dispatch",
        agent="mcp_act_gateway",
        metadata={"channel": "meta", "status": "published"},
    )
    # 7. Telemetry T30
    await recorder.record(
        tenant_id=tenant_id,
        entity_id="telemetry_batch:001",
        activity="telemetry_stored",
        agent="telemetry_engine",
        metadata={"task_id": "task-t30", "events_ingested": 25},
    )
    # 8. Learning T31
    await recorder.record(
        tenant_id=tenant_id,
        entity_id="attribution_model:linear",
        activity="attribution_and_decay_calculated",
        agent="W_LEARN",
        metadata={"task_id": "task-t31", "confidence": 0.88, "model": "linear"},
    )


# ============================================================================
# 1. Authoritative Dependencies Verification (T30, T31)
# ============================================================================

@pytest.mark.asyncio
async def test_t33_fails_closed_when_t30_missing() -> None:
    """T33 fails closed if prerequisite task-t30 is absent from CTS."""
    validator, recorder, _, task_states, caller, _ = _setup_t33_environment(has_t30=False)
    await _seed_full_pipeline_provenance(recorder)

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert isinstance(report, AuditValidationReport)
    assert report.is_valid is False
    assert report.t30_status == "MISSING"
    assert report.t34_audit_eligible is False
    assert any("task-t30" in g for g in report.detected_gaps)


@pytest.mark.asyncio
async def test_t33_fails_closed_when_t30_incomplete() -> None:
    """T33 fails closed if task-t30 is still in progress or unapproved."""
    validator, recorder, _, task_states, caller, _ = _setup_t33_environment(t30_status=TaskStatus.IN_PROGRESS)
    await _seed_full_pipeline_provenance(recorder)

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.is_valid is False
    assert report.t30_status == "in_progress"
    assert report.t34_audit_eligible is False
    assert any("task-t30 is not authoritatively accepted" in g for g in report.detected_gaps)


@pytest.mark.asyncio
async def test_t33_fails_closed_when_t31_missing() -> None:
    """T33 fails closed if prerequisite task-t31 is absent from CTS."""
    validator, recorder, _, task_states, caller, _ = _setup_t33_environment(has_t31=False)
    await _seed_full_pipeline_provenance(recorder)

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.is_valid is False
    assert report.t31_status == "MISSING"
    assert report.t34_audit_eligible is False
    assert any("task-t31" in g for g in report.detected_gaps)


@pytest.mark.asyncio
async def test_t33_fails_closed_when_t31_incomplete() -> None:
    """T33 fails closed if task-t31 is not completed or unapproved."""
    validator, recorder, _, task_states, caller, _ = _setup_t33_environment(t31_status=TaskStatus.FAILED)
    await _seed_full_pipeline_provenance(recorder)

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.is_valid is False
    assert report.t31_status == "failed"
    assert report.t34_audit_eligible is False
    assert any("task-t31 is not authoritatively accepted" in g for g in report.detected_gaps)


# ============================================================================
# 2. Model A Boundary: Caller Authority & Tenant Scope
# ============================================================================

@pytest.mark.asyncio
async def test_t33_rejects_worker_execution() -> None:
    """Worker or specialist agent calling T33 validation raises PolicyViolationError."""
    validator, _, _, task_states, _, _ = _setup_t33_environment()

    worker_caller = CallerIdentity(
        subject="W_LEARN",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.MEDIUM,
    )

    with pytest.raises(PolicyViolationError, match="Direct worker execution of T33.*forbidden"):
        await validator.validate_lineage_and_integrity(
            "tenant-alpha", task_states=task_states, caller=worker_caller
        )


@pytest.mark.asyncio
async def test_t33_enforces_caller_tenant_scope() -> None:
    """Caller with tenant scope mismatched from audit tenant raises ValueError."""
    validator, _, _, task_states, _, _ = _setup_t33_environment()

    mismatched_caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=TenantScope(tenant_id="tenant-beta"),
        risk_ceiling=RiskLevel.HIGH,
    )

    with pytest.raises(ValueError, match="Caller tenant scope.*does not match"):
        await validator.validate_lineage_and_integrity(
            "tenant-alpha", task_states=task_states, caller=mismatched_caller
        )


# ============================================================================
# 3. Cryptographic Ledger Integrity (Hash Chain, Ordering, Payload)
# ============================================================================

@pytest.mark.asyncio
async def test_t33_fails_closed_on_broken_previous_hash() -> None:
    """Broken previous-hash continuity between adjacent records fails validation."""
    validator, recorder, repo, task_states, caller, _ = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    # Corrupt prev_record_hash on 3rd record
    chain = repo._chains["tenant-alpha"]
    tampered_rec = chain[2].model_copy(update={"prev_record_hash": "corrupted_hash_xyz"})
    chain[2] = tampered_rec

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.is_valid is False
    assert report.hash_chain_verified is False
    assert any("Broken previous-hash continuity" in g for g in report.detected_gaps)


@pytest.mark.asyncio
async def test_t33_fails_closed_on_tampered_payload_or_metadata() -> None:
    """Tampering with record metadata or payload without updating hash fails validation."""
    validator, recorder, repo, task_states, caller, _ = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    # Tamper with metadata in-place
    chain = repo._chains["tenant-alpha"]
    chain[1].metadata["unauthorized_field"] = "forged_value"

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.is_valid is False
    assert report.hash_chain_verified is False
    assert any("Metadata/payload hash mismatch" in g for g in report.detected_gaps)


@pytest.mark.asyncio
async def test_t33_fails_closed_on_reordered_records() -> None:
    """Out-of-order timestamps in audit chain fail validation."""
    validator, recorder, repo, task_states, caller, _ = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    # Swap order / tamper timestamp backwards
    chain = repo._chains["tenant-alpha"]
    backdated = chain[4].model_copy(update={"occurred_at": chain[2].occurred_at - timedelta(hours=1)})
    chain[4] = backdated

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.is_valid is False
    assert report.hash_chain_verified is False
    assert any("Reordered records detected" in g for g in report.detected_gaps)


@pytest.mark.asyncio
async def test_t33_fails_closed_on_duplicate_record_id() -> None:
    """Duplicate record ID appearing twice in the chain fails validation."""
    validator, recorder, repo, task_states, caller, _ = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    chain = repo._chains["tenant-alpha"]
    dup = chain[0].model_copy()
    chain.append(dup)

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.is_valid is False
    assert report.hash_chain_verified is False
    assert any("Duplicate record ID" in g for g in report.detected_gaps)


@pytest.mark.asyncio
async def test_t33_fails_closed_on_cross_tenant_record() -> None:
    """Foreign tenant record leaked into audit chain fails validation."""
    validator, recorder, repo, task_states, caller, _ = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    chain = repo._chains["tenant-alpha"]
    foreign_rec = chain[1].model_copy(update={"tenant_id": "foreign-tenant"})
    chain[1] = foreign_rec

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.is_valid is False
    assert any("Cross-tenant record leak" in g for g in report.detected_gaps)


# ============================================================================
# 4. W3C PROV Graph & Relation Validation
# ============================================================================

@pytest.mark.asyncio
async def test_t33_fails_closed_on_orphan_w3c_prov_entities() -> None:
    """W3C PROV relation referencing an unknown/orphan entity fails validation."""
    validator, recorder, repo, task_states, caller, _ = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    # Find sandbox record with W3C PROV bundle
    chain = repo._chains["tenant-alpha"]
    sb_rec = [r for r in chain if r.w3c_prov and r.w3c_prov.get("relations")][0]

    # Inject dangling relation
    sb_rec.w3c_prov["relations"].append({
        "relation_type": ProvRelationType.USED.value,
        "source_id": "urn:enterprise_os:activity:sandbox_execution:exec-001:completed",
        "target_id": "nonexistent_orphan_entity_12345",
    })

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.is_valid is False
    assert report.prov_graph_valid is False
    assert any("Orphan relation target" in g for g in report.detected_gaps)


# ============================================================================
# 5. Cryptographic Signature Validation
# ============================================================================

@pytest.mark.asyncio
async def test_t33_validates_ed25519_signatures() -> None:
    """Valid cryptographic approval signatures on CTS clearances pass verification."""
    validator, recorder, _, task_states, caller, (priv_key, pub_pem) = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    # Create signed clearance in task state
    canon_bytes = b"preview-001|APPROVED|marketer|tenant-alpha|hash123"
    sig_b64 = sign_payload(canon_bytes, priv_key)

    task_states["task-t30"].cts_state["clearances"] = [{
        "preview_id": "prev-001",
        "signature": sig_b64,
        "public_key_pem": pub_pem,
        "canonical_bytes": canon_bytes.decode("utf-8"),
    }]

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.signatures_verified is True
    assert report.is_valid is True


@pytest.mark.asyncio
async def test_t33_fails_closed_on_invalid_ed25519_signature() -> None:
    """Corrupted or forged Ed25519 signature fails verification and marks validation invalid."""
    validator, recorder, _, task_states, caller, (_, pub_pem) = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    task_states["task-t30"].cts_state["clearances"] = [{
        "preview_id": "prev-001",
        "signature": "dGhpcyBpcyBhIGZha2Ugc2lnbmF0dXJlIHRoYXQgd2lsbCBmYWlsIQ==",
        "public_key_pem": pub_pem,
        "canonical_bytes": "preview-001|APPROVED|marketer|tenant-alpha|hash123",
    }]

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.is_valid is False
    assert report.signatures_verified is False
    assert any("Cryptographic signature verification failed" in g for g in report.detected_gaps)


# ============================================================================
# 6. CTS State Reconciliation
# ============================================================================

@pytest.mark.asyncio
async def test_t33_fails_closed_on_cts_provenance_mismatch() -> None:
    """A task marked COMPLETED in CTS with zero audit trace in provenance fails reconciliation."""
    validator, recorder, _, task_states, caller, _ = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    # Introduce phantom completed task
    task_states["task-phantom-999"] = CanonicalTaskState(
        task_id="task-phantom-999",
        directive_id="dir-phantom",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.COMPLETED,
        governance_approved=True,
    )

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    assert report.is_valid is False
    assert report.cts_reconciled is False
    assert any("task-phantom-999" in g for g in report.detected_gaps)


# ============================================================================
# 7. Successful End-to-End Lineage & Integrity Validation (T33 Acceptance)
# ============================================================================

@pytest.mark.asyncio
async def test_t33_successful_end_to_end_validation() -> None:
    """All stages verified, unbroken hash chain, intact W3C PROV graph, CTS reconciled -> T33 PASS."""
    validator, recorder, repo, task_states, caller, _ = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    initial_chain_length = len(repo._chains["tenant-alpha"])

    report = await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    # 1. Report verification
    assert isinstance(report, AuditValidationReport)
    assert report.is_valid is True
    assert report.t30_status == "ACCEPTED"
    assert report.t31_status == "ACCEPTED"
    assert report.hash_chain_verified is True
    assert report.signatures_verified is True
    assert report.cts_reconciled is True
    assert report.prov_graph_valid is True
    assert report.t34_audit_eligible is True
    assert len(report.detected_gaps) == 0

    # 2. Stage coverage verification
    assert AuditLineageStage.GOVERNANCE.value in report.stages_verified
    assert AuditLineageStage.ORCHESTRATION.value in report.stages_verified
    assert AuditLineageStage.RAG.value in report.stages_verified
    assert AuditLineageStage.WORKER_SANDBOX.value in report.stages_verified
    assert AuditLineageStage.HITL_APPROVAL.value in report.stages_verified
    assert AuditLineageStage.MCP_ACTUATION.value in report.stages_verified
    assert AuditLineageStage.TELEMETRY_T30.value in report.stages_verified
    assert AuditLineageStage.LEARNING_T31.value in report.stages_verified

    # 3. CTS task-t33 verification
    t33_task = task_states["task-t33"]
    assert t33_task.status == TaskStatus.COMPLETED
    assert t33_task.cts_state["audit_validation_id"] == report.validation_id
    assert t33_task.cts_state["is_valid"] is True
    assert t33_task.cts_state["t34_ready"] is True

    # 4. Provenance audit event appended without rewriting history
    updated_chain = repo._chains["tenant-alpha"]
    assert len(updated_chain) == initial_chain_length + 1
    audit_record = updated_chain[-1]
    assert audit_record.activity == "audit_lineage_validated"
    assert audit_record.agent == "W3C_PROV_AUDITOR"
    assert audit_record.prev_record_hash == updated_chain[-2].record_hash

    # Entire chain including validation record remains unbroken
    assert repo.verify(updated_chain) is True


# ============================================================================
# 8. Non-Destructive / Immutability Guarantee
# ============================================================================

@pytest.mark.asyncio
async def test_t33_historical_records_remain_immutable() -> None:
    """Validation never mutates, overwrites, or resequences prior audit records."""
    validator, recorder, repo, task_states, caller, _ = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    prior_chain_dump = [r.model_dump() for r in repo._chains["tenant-alpha"]]

    await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    current_chain = repo._chains["tenant-alpha"]
    # All prior records are identical down to timestamp and hashes
    for idx, prior_dump in enumerate(prior_chain_dump):
        assert current_chain[idx].model_dump() == prior_dump


# ============================================================================
# 9. Isolation: Zero T32 Promotion or T34 Closeout
# ============================================================================

@pytest.mark.asyncio
async def test_t33_zero_t32_or_t34_execution() -> None:
    """T33 validates audit lineage but never executes T32 memory promotion or T34 project closeout."""
    validator, recorder, repo, task_states, caller, _ = _setup_t33_environment()
    await _seed_full_pipeline_provenance(recorder)

    await validator.validate_lineage_and_integrity(
        "tenant-alpha", task_states=task_states, caller=caller
    )

    # Check zero T34 tasks created or completed
    assert "task-t34" not in task_states

    # Check zero memory promotion or closeout activities
    chain = repo._chains["tenant-alpha"]
    activities = [r.activity.lower() for r in chain]
    assert not any("memory_promote" in a for a in activities)
    assert not any("t34" in a for a in activities)
    assert not any("project_closeout" in a for a in activities)
