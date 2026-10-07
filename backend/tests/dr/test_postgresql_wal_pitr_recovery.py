"""PostgreSQL Base Backup + Continuous WAL Archiving + PITR Recovery Test Suite.

Proves:
1. Explicit RPO/RTO targets codified and evaluated for all 8 subsystems.
2. PostgreSQL base backup created with table snapshots, start/stop LSNs, and backup_label.
3. Continuous WAL archiving streams mutations into a tamper-evident vault with restore points.
4. Point-In-Time Recovery onto a separate clean host:
   - Restores base backup onto clean database.
   - Replays archived WAL up to exact recovery target point.
   - Discards post-cutoff transactions (proving point-in-time cutoff precision).
5. State Integrity Verification across all 6 invariants:
   - CTS versions remain strictly monotonic and CAS concurrency operational.
   - W3C PROV cryptographic hash chains verify 100% without breaks.
   - Tenant isolation remains intact across all stores.
   - Replayed specialist mandates are strictly rejected.
   - HITL decisions and Ed25519 signatures remain valid.
   - Promoted memory and telemetry strictly agree with the recovery point.
6. Actual measured RPO and RTO satisfy targets, rather than only asserting success.
7. Governing invariant upheld: failure never causes unauthorized actuation,
   duplicate irreversible action, lost audit lineage, cross-tenant leakage,
   false terminal CTS state, or silent data loss.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.core.settings import DatabaseSettings
from app.disaster_recovery.postgres_pitr_engine import PostgresPITREngine
from app.disaster_recovery.rpo_rto import (
    DisasterRecoveryTargetRegistry,
    DRCriticality,
    RecoveryStatus,
    SubsystemDomain,
)
from app.disaster_recovery.state_integrity_verifier import (
    EnterpriseOSStateIntegrityVerifier,
)
from app.disaster_recovery.wal_archive_vault import (
    RestorePoint,
    WALArchiveVault,
    WALRecord,
    WALSegment,
)
from app.integrations.sandbox.provisioner_daemon import (
    ReplayStateManager,
    SandboxProvisionerEngine,
)
from app.persistence.database import Database
from app.persistence.repositories.memory import MemoryRepository
from app.persistence.repositories.operational import OperationalRepository
from app.persistence.repositories.provenance import ProvenanceRepository
from app.persistence.repositories.task_state import TaskStateRepository
from app.persistence.repositories.telemetry import TelemetryRepository
from app.schemas.action_preview import ActionPreview, ActionPreviewKind
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.memory import MemoryNamespace, MemoryRecord
from app.schemas.sandbox import (
    NetworkPolicy,
    ResourceLimits,
    SandboxCapability,
    SandboxInvocationMandate,
)
from app.schemas.task_state import CanonicalTaskState, TaskCheckpoint, TaskStatus
from app.schemas.telemetry import TelemetryEvent, TelemetryEventType
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.hitl import canonical_decision_bytes

POSTGRES_PRIMARY_DSN = os.getenv(
    "ENTERPRISE_OS_PRIMARY_DSN",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/governed_backend",
)
POSTGRES_CLEAN_HOST_DSN = os.getenv(
    "ENTERPRISE_OS_CLEAN_HOST_DSN",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_os_clean_host_dr",
)


# =============================================================================
# TEST 1: Formal RPO/RTO Target Registry Specification Coverage
# =============================================================================
def test_dr_rpo_rto_target_registry_coverage() -> None:
    """Verify that all 8 architectural domains have explicit, formal RPO/RTO policies."""
    registry = DisasterRecoveryTargetRegistry()
    policies = registry.all_policies()

    expected_domains = {
        SubsystemDomain.POSTGRESQL,
        SubsystemDomain.CTS,
        SubsystemDomain.PROVENANCE,
        SubsystemDomain.REPLAY_STATE,
        SubsystemDomain.INSTITUTIONAL_MEMORY,
        SubsystemDomain.TELEMETRY,
        SubsystemDomain.PROVISIONER_RUNTIME,
        SubsystemDomain.RELEASE_ARTIFACTS,
    }

    assert set(policies.keys()) == expected_domains

    # Check PostgreSQL targets
    pg_policy = registry.get_policy(SubsystemDomain.POSTGRESQL)
    assert pg_policy.target_rpo_seconds <= 1.0
    assert pg_policy.target_rto_seconds <= 15.0
    assert pg_policy.criticality == DRCriticality.HIGH
    assert len(pg_policy.invariants) >= 3

    # Check CTS zero-loss target
    cts_policy = registry.get_policy(SubsystemDomain.CTS)
    assert cts_policy.target_rpo_seconds == 0.0
    assert cts_policy.criticality == DRCriticality.CRITICAL
    assert "strictly monotonic" in "".join(cts_policy.invariants)

    # Check Provenance zero-loss target
    prov_policy = registry.get_policy(SubsystemDomain.PROVENANCE)
    assert prov_policy.target_rpo_seconds == 0.0
    assert prov_policy.criticality == DRCriticality.CRITICAL

    # Check Replay State zero duplicate execution target
    replay_policy = registry.get_policy(SubsystemDomain.REPLAY_STATE)
    assert replay_policy.target_rpo_seconds == 0.0
    assert replay_policy.target_rto_seconds <= 2.0

    # Test metric evaluation helper
    metric_met = registry.evaluate_metric(
        SubsystemDomain.POSTGRESQL,
        measured_rpo_seconds=0.45,
        measured_rto_seconds=4.2,
        invariants_satisfied=["All checks passed"],
    )
    assert metric_met.rpo_met is True
    assert metric_met.rto_met is True
    assert metric_met.status == RecoveryStatus.TARGET_MET

    metric_violated = registry.evaluate_metric(
        SubsystemDomain.POSTGRESQL,
        measured_rpo_seconds=2.5,
        measured_rto_seconds=25.0,
        invariants_satisfied=[],
        invariants_violated=["RPO threshold breached"],
    )
    assert metric_violated.rpo_met is False
    assert metric_violated.rto_met is False
    assert metric_violated.status == RecoveryStatus.INVARIANT_FAILED


# =============================================================================
# TEST 2: Tamper-Evident WAL Archive Vault Integrity
# =============================================================================
def test_wal_archive_vault_immutability_and_tamper_detection(tmp_path: Path) -> None:
    """Verify that the WAL Archive Vault validates segment checksums and detects tampering."""
    vault_dir = tmp_path / "wal_vault"
    vault = WALArchiveVault(vault_dir)

    # 1. Base backup storage and verification
    manifest = vault.save_base_backup(
        backup_id="bkp-test-01",
        label="test_label",
        start_lsn="0/1000",
        stop_lsn="0/2000",
        start_time=datetime.now(UTC),
        stop_time=datetime.now(UTC),
        database_name="governed_backend",
        tables_data={"task_states": [{"id": "t1", "tenant_id": "tenant-a"}]},
    )
    assert manifest.backup_id == "bkp-test-01"
    assert manifest.sha256_checksum != ""

    loaded_manifest, loaded_data = vault.load_base_backup("bkp-test-01")
    assert loaded_manifest.backup_id == "bkp-test-01"
    assert loaded_data["task_states"][0]["id"] == "t1"

    # 2. Archive sequential WAL segments
    t1 = datetime.now(UTC)
    t2 = t1 + timedelta(seconds=1)
    rec1 = WALRecord(
        record_id="rec-1",
        lsn="0/2100",
        timestamp=t1,
        tenant_id="tenant-a",
        table_name="task_states",
        operation="INSERT",
        row_id="t2",
        data={"id": "t2"},
    )
    rec1.record_hash = rec1.compute_hash()

    seg1 = WALSegment(
        segment_id="00000001",
        segment_number=1,
        start_lsn="0/2000",
        end_lsn="0/2200",
        start_time=t1,
        end_time=t2,
        records=[rec1],
    )
    vault.archive_wal_segment(seg1)

    segments = vault.list_wal_segments()
    assert len(segments) == 1
    assert segments[0].segment_id == "00000001"

    # 3. Vault integrity verification
    vault_status = vault.verify_vault_integrity()
    assert vault_status["healthy"] is True
    assert vault_status["status"] == "VAULT_VERIFIED"

    # 4. Tampering detection: corrupt segment payload on disk
    seg_file = vault_dir / "wal_segments" / "00000001.wal.gz"
    seg_file.write_bytes(b"corrupted_garbage_bytes")

    with pytest.raises(Exception):
        vault.list_wal_segments()


# =============================================================================
# TEST 3: Full End-to-End PostgreSQL Base Backup + WAL + Clean Host PITR
# =============================================================================
@pytest.mark.asyncio
async def test_postgresql_wal_pitr_recovery_onto_clean_host(tmp_path: Path) -> None:
    """Execute complete workflow:
    1. Primary Host: Initial state + Base backup taken.
    2. Primary Host: Stage 1 operations committed + Restore point created at T_target.
    3. Primary Host: Post-cutoff Stage 2 operations committed at T_post (T_post > T_target).
    4. Simulate disaster on Primary Host.
    5. Clean Host: PITR restore from vault up to T_target.
    6. Verify all 6 invariants and measure actual RPO and RTO.
    7. Clean host destroyed.
    """
    vault_dir = tmp_path / "pitr_vault"
    replay_file = tmp_path / "replay_state.json"
    vault = WALArchiveVault(vault_dir)

    tenant_alpha = f"tenant-dr-alpha-{uuid.uuid4().hex[:6]}"
    tenant_beta = f"tenant-dr-beta-{uuid.uuid4().hex[:6]}"
    directive_id = f"dir-dr-{uuid.uuid4().hex[:6]}"
    task_id_alpha = f"task-cts-alpha-{uuid.uuid4().hex[:6]}"
    task_id_beta = f"task-cts-beta-{uuid.uuid4().hex[:6]}"

    # Prepare Ed25519 signing keypair for HITL verification
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_pem = priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    crypto_validator = CryptographicValidator(public_key_pem=pub_pem)

    # =========================================================================
    # PHASE 1: Connect to Primary Host & Apply Migrations
    # =========================================================================
    primary_db = Database(
        DatabaseSettings(
            dsn=POSTGRES_PRIMARY_DSN,
            enforce_rls=False,
            require_non_privileged_role=False,
        )
    )
    await primary_db.apply_migrations()

    pitr_engine = PostgresPITREngine(source_dsn=POSTGRES_PRIMARY_DSN, vault=vault)
    op_repo = OperationalRepository(primary_db.session_factory)
    ts_repo = TaskStateRepository(primary_db.session_factory)
    prov_repo = ProvenanceRepository(primary_db.session_factory)
    mem_repo = MemoryRepository(primary_db.session_factory)
    tel_repo = TelemetryRepository(primary_db.session_factory)

    # Provisioner engine for specialist execution
    provisioner_engine = SandboxProvisionerEngine(replay_state_path=replay_file)

    # Pre-backup state: Initial directive and initial tasks
    directive = Directive(
        directive_id=directive_id,
        tenant_id=tenant_alpha,
        objective="Disaster Recovery certification with full PITR state integrity",
        budget_cap=50000.0,
        risk_ceiling=RiskLevel.MEDIUM,
        scope=TenantScope(
            tenant_id=tenant_alpha,
            brand_ids=["brand-dr"],
            allowed_channels=["web"],
        ),
    )
    await op_repo.save_directive(directive)

    task_alpha_init = CanonicalTaskState(
        task_id=task_id_alpha,
        directive_id=directive_id,
        tenant_id=tenant_alpha,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.IN_PROGRESS,
        version=1,
        checkpoints=[
            TaskCheckpoint(
                checkpoint_id=f"chk-0-{uuid.uuid4().hex[:6]}",
                task_id=task_id_alpha,
                status=TaskStatus.IN_PROGRESS,
                note="Base initialization",
            )
        ],
    )
    await ts_repo.save_state(tenant_alpha, task_alpha_init)

    # Initial provenance record
    prov_rec_0 = await prov_repo.append(
        tenant_id=tenant_alpha,
        entity_id=task_id_alpha,
        activity="TASK_INIT",
        agent="W_ORCHESTRATOR",
        metadata={"phase": "pre_backup"},
    )

    # =========================================================================
    # PHASE 2: Take Base Backup
    # =========================================================================
    backup_manifest = await pitr_engine.create_base_backup(
        backup_id="base-bkp-primary-01",
        label="enterprise_os_pitr_baseline",
    )
    assert backup_manifest.backup_id == "base-bkp-primary-01"
    assert backup_manifest.table_counts["task_states"] >= 1

    # =========================================================================
    # PHASE 3: Execute Stage 1 (Pre-Disaster / Target Recovery Window)
    # =========================================================================
    time_before_stage1 = datetime.now(UTC)

    # 1. Monotonic CTS update on Alpha (version 1 -> version 2)
    task_alpha_v2 = CanonicalTaskState(
        task_id=task_id_alpha,
        directive_id=directive_id,
        tenant_id=tenant_alpha,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.AWAITING_APPROVAL,
        version=2,
        checkpoints=[
            task_alpha_init.checkpoints[0],
            TaskCheckpoint(
                checkpoint_id=f"chk-1-{uuid.uuid4().hex[:6]}",
                task_id=task_id_alpha,
                status=TaskStatus.AWAITING_APPROVAL,
                note="Budget allocation complete, pending HITL clearance",
            ),
        ],
    )
    cas_v2 = await ts_repo.compare_and_swap_state(
        tenant_id=tenant_alpha, expected_version=1, state=task_alpha_v2
    )
    assert cas_v2 is True
    await pitr_engine.record_transaction(
        tenant_id=tenant_alpha,
        table_name="task_states",
        operation="UPDATE",
        row_id=task_id_alpha,
        data={"document": task_alpha_v2.model_dump(mode="json")},
    )

    # 2. Append Provenance Block 2 (chains to Block 0)
    prov_rec_1 = await prov_repo.append(
        tenant_id=tenant_alpha,
        entity_id=task_id_alpha,
        activity="ALLOCATE_BUDGET",
        agent="W_STRAT",
        metadata={"allocated": 10000.0},
    )
    assert prov_rec_1.prev_record_hash == prov_rec_0.record_hash
    await pitr_engine.record_transaction(
        tenant_id=tenant_alpha,
        table_name="provenance_records",
        operation="INSERT",
        row_id=prov_rec_1.record_id,
        data={"document": prov_rec_1.model_dump(mode="json")},
    )

    # 3. Provenance for Beta (proving multi-tenant independence)
    prov_beta = await prov_repo.append(
        tenant_id=tenant_beta,
        entity_id=task_id_beta,
        activity="INIT_BETA",
        agent="W_STRAT",
        metadata={"tenant": "beta"},
    )
    await pitr_engine.record_transaction(
        tenant_id=tenant_beta,
        table_name="provenance_records",
        operation="INSERT",
        row_id=prov_beta.record_id,
        data={"document": prov_beta.model_dump(mode="json")},
    )

    # 4. Specialist Execution via Provisioner
    exec_id_1 = f"exec-spec-01-{uuid.uuid4().hex[:6]}"
    mandate_1 = SandboxInvocationMandate(
        execution_id=exec_id_1,
        task_id=task_id_alpha,
        tenant_id=tenant_alpha,
        stage_attempt_id="att-spec-01",
        worker_role="W_STRAT",
        capability=SandboxCapability.ALLOC,
        operation="allocate_budget",
        payload={"total_budget": 10000.0, "channels": ["web"], "constraints": {"min_allocation": 100.0}},
        resource_limits=ResourceLimits(cpu_cores=1.0, memory_mb=256),
        network_policy=NetworkPolicy.DISABLED,
    )
    result_1 = provisioner_engine.execute(mandate_1)
    assert result_1.success is True
    assert result_1.execution_receipt is not None

    # 5. Promoted Institutional Memory 1
    mem_id_1 = f"mem-dr-01-{uuid.uuid4().hex[:6]}"
    mem_1 = MemoryRecord(
        memory_id=mem_id_1,
        tenant_id=tenant_alpha,
        category="strategy",
        statement="optimal budget allocation verified at 10000.0",
        namespace=MemoryNamespace.ATTRIBUTION_HEURISTICS.value,
        title="budget_allocation_rule_v1",
        confidence=0.95,
        metadata={"source_execution_id": exec_id_1},
    )
    await mem_repo.promote(mem_1)
    await pitr_engine.record_transaction(
        tenant_id=tenant_alpha,
        table_name="institutional_memory",
        operation="INSERT",
        row_id=mem_id_1,
        data={"document": mem_1.model_dump(mode="json")},
    )

    # 6. Telemetry Event 1
    tel_id_1 = f"tel-dr-01-{uuid.uuid4().hex[:6]}"
    tel_1 = TelemetryEvent(
        event_id=tel_id_1,
        tenant_id=tenant_alpha,
        event_type=TelemetryEventType.TRAFFIC,
        channel="web",
        occurred_at=datetime.now(UTC),
        metrics={"duration_ms": float(result_1.execution_duration_ms)},
    )
    await tel_repo.record(tel_1)
    await pitr_engine.record_transaction(
        tenant_id=tenant_alpha,
        table_name="telemetry_events",
        operation="INSERT",
        row_id=tel_id_1,
        data={"document": tel_1.model_dump(mode="json")},
    )

    # 7. HITL Signed Approval Clearance 1
    preview_id_1 = f"prev-dr-{uuid.uuid4().hex[:6]}"
    content_hash_1 = "sha256:abc123mockcontenthash001"
    decided_at_str_1 = datetime.now(UTC).isoformat()
    canonical_bytes_1 = canonical_decision_bytes(
        preview_id=preview_id_1,
        decision="approve",
        approver="auditor@enterprise.internal",
        tenant_id=tenant_alpha,
        preview_content_hash=content_hash_1,
        decided_at=decided_at_str_1,
    )
    sig_1 = sign_payload(canonical_bytes_1, priv_key)
    hitl_decision_1 = {
        "preview_id": preview_id_1,
        "decision": "approve",
        "approver": "auditor@enterprise.internal",
        "tenant_id": tenant_alpha,
        "preview_content_hash": content_hash_1,
        "decided_at": decided_at_str_1,
        "signature": sig_1,
    }

    # CREATE RESTORE POINT AT THIS EXACT STATE
    await asyncio.sleep(0.05)  # Ensure clock advances slightly
    target_restore_point = await pitr_engine.create_restore_point("RESTORE_PT_CLEAN_STG1")
    recovery_target_time = target_restore_point.timestamp
    assert target_restore_point.name == "RESTORE_PT_CLEAN_STG1"

    # =========================================================================
    # PHASE 4: Execute Post-Cutoff Mutations (Must NOT be present after restore!)
    # =========================================================================
    await asyncio.sleep(0.05)  # Distinct timestamp past cutoff

    # Post-cutoff CTS mutation (advancing to version 3)
    task_alpha_v3 = CanonicalTaskState(
        task_id=task_id_alpha,
        directive_id=directive_id,
        tenant_id=tenant_alpha,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.COMPLETED,
        version=3,
        checkpoints=[
            task_alpha_v2.checkpoints[0],
            task_alpha_v2.checkpoints[1],
            TaskCheckpoint(
                checkpoint_id=f"chk-2-{uuid.uuid4().hex[:6]}",
                task_id=task_id_alpha,
                status=TaskStatus.COMPLETED,
                note="Post-disaster uncommitted task completion",
            ),
        ],
    )
    await ts_repo.compare_and_swap_state(
        tenant_id=tenant_alpha, expected_version=2, state=task_alpha_v3
    )
    await pitr_engine.record_transaction(
        tenant_id=tenant_alpha,
        table_name="task_states",
        operation="UPDATE",
        row_id=task_id_alpha,
        data={"document": task_alpha_v3.model_dump(mode="json")},
    )

    # Post-cutoff memory promotion
    post_cutoff_mem_id = f"mem-post-cutoff-{uuid.uuid4().hex[:6]}"
    mem_post = MemoryRecord(
        memory_id=post_cutoff_mem_id,
        tenant_id=tenant_alpha,
        category="strategy",
        statement="post-disaster uncommitted hallucinated rule",
        namespace=MemoryNamespace.ATTRIBUTION_HEURISTICS.value,
        title="post_disaster_rule",
        confidence=0.88,
    )
    await mem_repo.promote(mem_post)
    await pitr_engine.record_transaction(
        tenant_id=tenant_alpha,
        table_name="institutional_memory",
        operation="INSERT",
        row_id=post_cutoff_mem_id,
        data={"document": mem_post.model_dump(mode="json")},
    )

    # Post-cutoff telemetry event
    post_cutoff_tel_id = f"tel-post-cutoff-{uuid.uuid4().hex[:6]}"
    tel_post = TelemetryEvent(
        event_id=post_cutoff_tel_id,
        tenant_id=tenant_alpha,
        event_type=TelemetryEventType.TRAFFIC,
        channel="web",
        occurred_at=datetime.now(UTC),
        metrics={"post_cutoff": 1.0},
    )
    await tel_repo.record(tel_post)
    await pitr_engine.record_transaction(
        tenant_id=tenant_alpha,
        table_name="telemetry_events",
        operation="INSERT",
        row_id=post_cutoff_tel_id,
        data={"document": tel_post.model_dump(mode="json")},
    )

    # Flush all remaining WAL to vault
    pitr_engine.flush_wal_segment()

    # =========================================================================
    # PHASE 5: Simulate Host 1 Disaster & Process Teardown
    # =========================================================================
    # Kill database pool simulating primary database host crash
    await primary_db.dispose()

    # =========================================================================
    # PHASE 6: Restore onto Separate Clean Host via PITR
    # =========================================================================
    clean_host_id = "clean_host_beta_recovery"
    receipt = await pitr_engine.restore_to_clean_host(
        clean_host_id=clean_host_id,
        clean_dsn=POSTGRES_CLEAN_HOST_DSN,
        base_backup_id="base-bkp-primary-01",
        recovery_target_name="RESTORE_PT_CLEAN_STG1",
        source_host_id="primary_host_alpha",
    )

    assert receipt.verdict == RecoveryStatus.CERTIFIED
    assert receipt.target_clean_host == clean_host_id
    assert receipt.overall_rto_seconds <= 15.0, f"RTO {receipt.overall_rto_seconds} breached target!"
    assert receipt.overall_rpo_seconds <= 1.0, f"RPO {receipt.overall_rpo_seconds} breached target!"

    # =========================================================================
    # PHASE 7: Verify Enterprise OS State Integrity on Recovered Clean Host
    # =========================================================================
    clean_db = Database(
        DatabaseSettings(
            dsn=POSTGRES_CLEAN_HOST_DSN,
            enforce_rls=False,
            require_non_privileged_role=False,
        )
    )
    verifier = EnterpriseOSStateIntegrityVerifier(clean_db=clean_db)

    # 1. Verify CTS Monotonicity:
    # Task must be at version 2 (Stage 1), NOT version 3 (post-cutoff)
    rec_task_alpha = await verifier.ts_repo.require(task_id_alpha)
    assert rec_task_alpha.version == 2
    assert rec_task_alpha.status == TaskStatus.AWAITING_APPROVAL

    cts_result = await verifier.verify_cts_monotonicity(
        tenant_ids=[tenant_alpha],
        reference_tasks={task_id_alpha: task_alpha_v2},
    )
    assert cts_result["passed"] is True, f"CTS monotonicity failed: {cts_result}"

    # 2. Verify W3C PROV Chains:
    prov_result = await verifier.verify_w3c_prov_chains(
        tenant_ids=[tenant_alpha, tenant_beta]
    )
    assert prov_result["passed"] is True, f"W3C PROV chain failed: {prov_result}"

    # 3. Verify Tenant Isolation:
    isolation_result = await verifier.verify_tenant_isolation(tenant_alpha, tenant_beta)
    assert isolation_result["passed"] is True, f"Tenant isolation failed: {isolation_result}"

    # 4. Verify Replay Protection Invariant:
    replay_result = verifier.verify_replay_protection_invariant(
        replay_state_path=replay_file,
        executed_mandates=[mandate_1],
    )
    assert replay_result["passed"] is True, f"Replay defense failed: {replay_result}"

    # 5. Verify HITL Decisions & Ed25519 Signatures:
    hitl_result = verifier.verify_hitl_decisions_and_signatures(
        decisions=[hitl_decision_1],
        validator=crypto_validator,
    )
    assert hitl_result["passed"] is True, f"HITL signature check failed: {hitl_result}"

    # 6. Verify Memory and Telemetry Agreement with Point-in-Time:
    # Memory 1 & Telemetry 1 must exist; post-cutoff memory & telemetry must NOT exist!
    mem_tel_result = await verifier.verify_memory_and_telemetry_agreement(
        tenant_ids=[tenant_alpha],
        recovery_target_time=recovery_target_time,
        post_cutoff_memory_ids=[post_cutoff_mem_id],
        post_cutoff_event_ids=[post_cutoff_tel_id],
    )
    assert mem_tel_result["passed"] is True, f"Memory/telemetry point-in-time failed: {mem_tel_result}"

    # 7. Full Certification Suite Run
    full_cert = await verifier.run_full_certification(
        tenant_alpha=tenant_alpha,
        tenant_beta=tenant_beta,
        recovery_target_time=recovery_target_time,
        replay_state_path=replay_file,
        executed_mandates=[mandate_1],
        hitl_decisions=[hitl_decision_1],
        crypto_validator=crypto_validator,
        post_cutoff_memories=[post_cutoff_mem_id],
        post_cutoff_telemetry=[post_cutoff_tel_id],
    )
    assert full_cert["certification_status"] == "PASSED"
    assert full_cert["governing_invariant_upheld"] is True

    # =========================================================================
    # PHASE 8: Clean Host Teardown
    # =========================================================================
    await clean_db.dispose()
    norm_admin = POSTGRES_PRIMARY_DSN.replace("postgresql+asyncpg://", "postgresql://").rsplit("/", 1)[0] + "/postgres"
    conn_admin = await asyncpg.connect(norm_admin)
    try:
        await conn_admin.execute("DROP DATABASE IF EXISTS enterprise_os_clean_host_dr;")
    finally:
        await conn_admin.close()
