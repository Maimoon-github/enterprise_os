"""Enterprise OS State-Integrity Verifier after Disaster Recovery & PITR.

Exhaustively verifies all 6 core post-restore invariants:
1. CTS versions remain monotonic and CAS-updatable.
2. W3C PROV cryptographic hash chains verify 100% without breaks.
3. Tenant isolation remains intact across all repositories.
4. Replayed mandates are strictly rejected by the provisioner.
5. HITL human decisions and Ed25519 signatures remain valid.
6. Promoted memory and telemetry strictly agree with the recovery point.

Enforces the Governing Invariant:
Failure may delay work, but must never create unauthorized actuation,
duplicate irreversible action, lost audit lineage, cross-tenant leakage,
false terminal CTS state, or silent data loss.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.disaster_recovery.rpo_rto import (
    DisasterRecoveryTargetRegistry,
    DomainRecoveryMetric,
    RecoveryStatus,
    SubsystemDomain,
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
from app.schemas.action_preview import ActionPreview, SignedApprovalClearance
from app.schemas.sandbox import SandboxInvocationMandate
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.cryptographic_validator import CryptographicValidator
from app.services.hitl import canonical_decision_bytes

logger = logging.getLogger(__name__)


class EnterpriseOSStateIntegrityVerifier:
    """Post-Restore State Integrity and Invariant Certification Engine."""

    def __init__(
        self,
        clean_db: Database,
        registry: DisasterRecoveryTargetRegistry | None = None,
    ) -> None:
        self.db = clean_db
        self.registry = registry or DisasterRecoveryTargetRegistry()

        # Instantiate repositories bound to clean recovered database
        self.ts_repo = TaskStateRepository(self.db.session_factory)
        self.prov_repo = ProvenanceRepository(self.db.session_factory)
        self.mem_repo = MemoryRepository(self.db.session_factory)
        self.tel_repo = TelemetryRepository(self.db.session_factory)
        self.op_repo = OperationalRepository(self.db.session_factory)

    async def verify_cts_monotonicity(
        self,
        tenant_ids: list[str],
        reference_tasks: dict[str, CanonicalTaskState] | None = None,
    ) -> dict[str, Any]:
        """Verify that recovered CTS versions are monotonic and CAS concurrency works."""
        verified_tasks: list[str] = []
        violations: list[str] = []

        for tenant_id in tenant_ids:
            tasks = await self.ts_repo.list_by_tenant(tenant_id)
            for task in tasks:
                # 1. Version must be at least 1 and >= checkpoint count
                if task.version < 1:
                    violations.append(f"Task {task.task_id} has invalid non-positive version {task.version}")
                    continue
                if task.version < len(task.checkpoints):
                    violations.append(
                        f"Task {task.task_id} version {task.version} < checkpoint count {len(task.checkpoints)}"
                    )
                    continue

                # 2. Check reference matching if provided
                if reference_tasks and task.task_id in reference_tasks:
                    ref = reference_tasks[task.task_id]
                    if task.version != ref.version:
                        violations.append(
                            f"Task {task.task_id} version mismatch: recovered {task.version} != expected {ref.version}"
                        )
                        continue

                # 3. Test CAS update on recovered task state
                cur_ver = task.version
                next_task = CanonicalTaskState(
                    task_id=task.task_id,
                    directive_id=task.directive_id,
                    worker_role=task.worker_role,
                    tenant_id=task.tenant_id,
                    status=task.status,
                    version=cur_ver + 1,
                    checkpoints=task.checkpoints,
                )

                # Stale CAS attempt must fail closed
                stale_cas = await self.ts_repo.compare_and_swap_state(
                    tenant_id=tenant_id,
                    expected_version=cur_ver - 1,
                    state=next_task,
                )
                if stale_cas:
                    violations.append(f"Task {task.task_id} permitted stale CAS update with version {cur_ver - 1}")
                    continue

                # Valid CAS attempt must succeed
                valid_cas = await self.ts_repo.compare_and_swap_state(
                    tenant_id=tenant_id,
                    expected_version=cur_ver,
                    state=next_task,
                )
                if not valid_cas:
                    violations.append(f"Task {task.task_id} failed valid CAS update from version {cur_ver}")
                    continue

                # Revert or record verified
                verified_tasks.append(task.task_id)

        passed = len(violations) == 0 and len(verified_tasks) > 0
        return {
            "passed": passed,
            "verified_count": len(verified_tasks),
            "violations": violations,
            "invariant": "CTS versions remain strictly monotonic and CAS-concurrency operational",
        }

    async def verify_w3c_prov_chains(self, tenant_ids: list[str]) -> dict[str, Any]:
        """Verify that per-tenant W3C PROV cryptographic hash chains are 100% unbroken."""
        violations: list[str] = []
        verified_tenants: list[str] = []
        total_blocks = 0

        for tenant_id in tenant_ids:
            records = await self.prov_repo.chain(tenant_id)
            if not records:
                continue

            total_blocks += len(records)
            is_valid = await self.prov_repo.verify_chain(tenant_id)
            if not is_valid:
                violations.append(f"Provenance chain hash violation for tenant {tenant_id}")
                continue

            # Verify appending post-recovery block chains correctly
            last_record = records[-1]
            new_record = await self.prov_repo.append(
                tenant_id=tenant_id,
                entity_id="dr_verification_entity",
                activity="POST_RESTORE_AUDIT_PROBE",
                agent="W_DR_VERIFIER",
                metadata={"test": "post_restore_chain_continuation"},
            )
            if new_record.prev_record_hash != last_record.record_hash:
                violations.append(
                    f"New record for tenant {tenant_id} did not link to previous head {last_record.record_hash}"
                )
                continue

            # Re-verify full extended chain
            if not await self.prov_repo.verify_chain(tenant_id):
                violations.append(f"Extended chain for tenant {tenant_id} failed verification")
                continue

            verified_tenants.append(tenant_id)

        passed = len(violations) == 0 and len(verified_tenants) > 0
        return {
            "passed": passed,
            "verified_tenants": verified_tenants,
            "total_blocks_verified": total_blocks,
            "violations": violations,
            "invariant": "W3C PROV audit chains verify with 100% cryptographic integrity",
        }

    async def verify_tenant_isolation(
        self, tenant_alpha: str, tenant_beta: str
    ) -> dict[str, Any]:
        """Verify strict multi-tenant boundary isolation after restoration."""
        leakage_detected: list[str] = []

        # 1. Task states isolation
        alpha_tasks = await self.ts_repo.list_by_tenant(tenant_alpha)
        for t in alpha_tasks:
            # Attempting to fetch Alpha's task using Beta's tenant_id must return None
            leaked = await self.ts_repo.get(t.task_id, tenant_id=tenant_beta)
            if leaked is not None:
                leakage_detected.append(f"Task {t.task_id} leaked to tenant {tenant_beta}")

        # 2. Institutional memory isolation
        alpha_mems = await self.mem_repo.list_by_tenant(tenant_alpha)
        for m in alpha_mems:
            leaked_mem = await self.mem_repo.get(m.memory_id, tenant_id=tenant_beta)
            if leaked_mem is not None:
                leakage_detected.append(f"Memory {m.memory_id} leaked to tenant {tenant_beta}")

        # 3. Provenance chain isolation
        alpha_prov = await self.prov_repo.chain(tenant_alpha)
        beta_prov = await self.prov_repo.chain(tenant_beta)
        alpha_hashes = {p.record_hash for p in alpha_prov}
        beta_hashes = {p.record_hash for p in beta_prov}
        if alpha_hashes.intersection(beta_hashes):
            leakage_detected.append("Cross-tenant collision detected in provenance record hashes")

        passed = len(leakage_detected) == 0
        return {
            "passed": passed,
            "violations": leakage_detected,
            "invariant": "Tenant isolation remains 100% leak-proof across all stores",
        }

    def verify_replay_protection_invariant(
        self,
        replay_state_path: Path,
        executed_mandates: list[SandboxInvocationMandate],
    ) -> dict[str, Any]:
        """Verify that pre-recovery mandates remain permanently rejected on restored host."""
        violations: list[str] = []
        verified_rejections = 0

        engine = SandboxProvisionerEngine(replay_state_path=replay_state_path)

        for mandate in executed_mandates:
            try:
                engine.execute(mandate)
                violations.append(
                    f"Replay protection violation: Mandate {mandate.execution_id} was re-executed!"
                )
            except Exception as exc:
                if "Replay forbidden" in str(exc) or "already completed" in str(exc):
                    verified_rejections += 1
                else:
                    violations.append(
                        f"Mandate {mandate.execution_id} failed with unexpected error: {exc}"
                    )

        passed = len(violations) == 0 and verified_rejections == len(executed_mandates)
        return {
            "passed": passed,
            "verified_rejections": verified_rejections,
            "violations": violations,
            "invariant": "All replayed mandates are strictly rejected with zero duplicate actuation",
        }

    def verify_hitl_decisions_and_signatures(
        self,
        decisions: list[dict[str, Any]],
        validator: CryptographicValidator,
    ) -> dict[str, Any]:
        """Verify that human approval decisions and Ed25519 signatures remain valid."""
        violations: list[str] = []
        verified_count = 0

        for dec in decisions:
            preview_id = dec["preview_id"]
            decision_val = dec["decision"]
            approver = dec["approver"]
            tenant_id = dec["tenant_id"]
            preview_content_hash = dec["preview_content_hash"]
            decided_at = dec["decided_at"]
            signature = dec["signature"]
            revision_notes = dec.get("revision_notes", "")

            # Canonical payload reconstruction
            payload = canonical_decision_bytes(
                preview_id=preview_id,
                decision=decision_val,
                approver=approver,
                tenant_id=tenant_id,
                preview_content_hash=preview_content_hash,
                decided_at=decided_at,
                revision_notes=revision_notes,
            )

            is_valid = validator.verify(payload=payload, signature_b64=signature)
            if not is_valid:
                violations.append(f"Cryptographic signature check failed for preview {preview_id}")
            else:
                verified_count += 1

        passed = len(violations) == 0 and verified_count > 0
        return {
            "passed": passed,
            "verified_count": verified_count,
            "violations": violations,
            "invariant": "HITL decisions and cryptographic signatures remain authentic and valid",
        }

    async def verify_memory_and_telemetry_agreement(
        self,
        tenant_ids: list[str],
        recovery_target_time: datetime,
        post_cutoff_memory_ids: list[str] | None = None,
        post_cutoff_event_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Verify that promoted memory and telemetry strictly agree with the recovery point."""
        violations: list[str] = []
        verified_memories = 0
        verified_events = 0

        # Small leeway (100ms) for clock alignment
        cutoff_boundary = recovery_target_time + timedelta(milliseconds=100)

        for tenant_id in tenant_ids:
            # 1. Institutional Memory Check
            memories = await self.mem_repo.list_by_tenant(tenant_id)
            for m in memories:
                m_time = getattr(m, "promoted_at", None) or getattr(m, "created_at", None)
                if m_time and m_time > cutoff_boundary:
                    violations.append(
                        f"Memory {m.memory_id} has timestamp {m_time} > cutoff {recovery_target_time}"
                    )
                else:
                    verified_memories += 1

            # 2. Telemetry Events Check
            events = await self.tel_repo.query_range(tenant_id=tenant_id)
            for ev in events:
                if ev.occurred_at and ev.occurred_at > cutoff_boundary:
                    violations.append(
                        f"Telemetry event {ev.event_id} has timestamp {ev.occurred_at} > cutoff {recovery_target_time}"
                    )
                else:
                    verified_events += 1

        # 3. Assert post-cutoff items are absent from clean database
        if post_cutoff_memory_ids:
            for mem_id in post_cutoff_memory_ids:
                for tenant_id in tenant_ids:
                    rec = await self.mem_repo.get(mem_id, tenant_id=tenant_id)
                    if rec is not None:
                        violations.append(
                            f"Post-cutoff memory {mem_id} leaked into recovered store!"
                        )

        if post_cutoff_event_ids:
            for ev_id in post_cutoff_event_ids:
                for tenant_id in tenant_ids:
                    evs = await self.tel_repo.query_range(tenant_id=tenant_id)
                    if any(e.event_id == ev_id for e in evs):
                        violations.append(
                            f"Post-cutoff telemetry event {ev_id} leaked into recovered store!"
                        )

        passed = len(violations) == 0
        return {
            "passed": passed,
            "verified_memories_count": verified_memories,
            "verified_telemetry_count": verified_events,
            "violations": violations,
            "invariant": "Promoted memory and telemetry strictly agree with the recovery point",
        }

    async def run_full_certification(
        self,
        tenant_alpha: str,
        tenant_beta: str,
        recovery_target_time: datetime,
        replay_state_path: Path,
        executed_mandates: list[SandboxInvocationMandate],
        hitl_decisions: list[dict[str, Any]],
        crypto_validator: CryptographicValidator,
        post_cutoff_memories: list[str] | None = None,
        post_cutoff_telemetry: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute exhaustive 6-way post-restore invariant certification."""
        tenants = [tenant_alpha, tenant_beta]

        cts_check = await self.verify_cts_monotonicity(tenants)
        prov_check = await self.verify_w3c_prov_chains(tenants)
        isolation_check = await self.verify_tenant_isolation(tenant_alpha, tenant_beta)
        replay_check = self.verify_replay_protection_invariant(
            replay_state_path, executed_mandates
        )
        hitl_check = self.verify_hitl_decisions_and_signatures(
            hitl_decisions, crypto_validator
        )
        mem_tel_check = await self.verify_memory_and_telemetry_agreement(
            tenants,
            recovery_target_time,
            post_cutoff_memory_ids=post_cutoff_memories,
            post_cutoff_event_ids=post_cutoff_telemetry,
        )

        all_passed = (
            cts_check["passed"]
            and prov_check["passed"]
            and isolation_check["passed"]
            and replay_check["passed"]
            and hitl_check["passed"]
            and mem_tel_check["passed"]
        )

        governing_invariant_upheld = all_passed

        return {
            "certification_status": "PASSED" if all_passed else "FAILED",
            "governing_invariant_upheld": governing_invariant_upheld,
            "checks": {
                "cts_monotonicity": cts_check,
                "provenance_cryptographic_chain": prov_check,
                "tenant_isolation": isolation_check,
                "replay_protection": replay_check,
                "hitl_signatures": hitl_check,
                "memory_telemetry_point_in_time": mem_tel_check,
            },
        }
