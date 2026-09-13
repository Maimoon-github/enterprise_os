"""Coordinates CTS persistence, checkpoints, locks, and exceptions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import InvalidTransitionError
from app.orchestration.task_state_machine import TaskStateMachine
from app.persistence.repositories.task_state import TaskStateRepository
from app.schemas.action_preview import (
    ActionPreviewDossier,
    HumanDecisionType,
    ReviewStatus,
    compute_preview_hash,
)
from app.schemas.agent_contracts import ConsolidatedEvidencePackage
from app.schemas.task_state import CanonicalTaskState, MilestoneCheckpoint, MilestoneStatus, TaskStatus
from app.security.cryptographic_validator import CryptographicValidator
from app.services.hitl import CATEGORY_ROLE_PERMISSIONS, HitlCoordinator, canonical_decision_bytes
from app.services.provenance import ProvenanceRecorder


class TaskStateService:
    """Coordinates Canonical Task State (CTS) lifecycle, persistence, checkpoints, and recovery."""

    def __init__(
        self,
        repository: TaskStateRepository | Any,
        state_machine: TaskStateMachine | None = None,
        provenance_recorder: ProvenanceRecorder | None = None,
        *,
        max_retries: int = 3,
    ) -> None:
        self._repository = repository
        self._state_machine = state_machine or TaskStateMachine()
        self._provenance_recorder = provenance_recorder
        self._max_retries = max_retries
        self._retry_counts: dict[str, int] = {}

    async def get_state(self, task_id: str) -> CanonicalTaskState:
        """Fetch the authoritative task state from repository."""
        return await self._repository.require(task_id)

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        """Persist state directly to repository."""
        await self._repository.save_state(tenant_id, state)

    async def transition(
        self,
        tenant_id: str,
        current_state: CanonicalTaskState,
        new_status: TaskStatus,
        *,
        note: str = "",
    ) -> CanonicalTaskState:
        """Validate transition, generate immutable checkpoint, and persist."""
        checkpoint_id = str(uuid.uuid4())
        updated = self._state_machine.transition(
            current_state, new_status, checkpoint_id=checkpoint_id, note=note
        )
        await self._repository.save_state(tenant_id, updated)
        if self._provenance_recorder:
            await self._provenance_recorder.record(
                tenant_id=tenant_id,
                entity_id=updated.task_id,
                activity=f"task_transition_{new_status.value}",
                agent="cts_state_machine",
            )
        return updated

    async def hold_task(
        self,
        tenant_id: str,
        task_id: str,
        reason: str,
    ) -> CanonicalTaskState:
        """Place task on hold with explicit reason."""
        state = await self.get_state(task_id)
        return await self.transition(tenant_id, state, TaskStatus.HELD, note=reason)

    async def resume_task(
        self,
        tenant_id: str,
        task_id: str,
        target_status: TaskStatus = TaskStatus.PENDING,
        note: str = "Resumed after hold review",
    ) -> CanonicalTaskState:
        """Resume a held task to an allowed target status."""
        state = await self.get_state(task_id)
        if state.status != TaskStatus.HELD:
            raise InvalidTransitionError(f"Task {task_id} is in status {state.status.value}, not HELD.")
        return await self.transition(tenant_id, state, target_status, note=note)

    async def handle_task_failure(
        self,
        tenant_id: str,
        task_id: str,
        error_message: str,
    ) -> CanonicalTaskState:
        """Handle execution exception by recording retry and placing on hold or failing."""
        count = self._retry_counts.get(task_id, 0) + 1
        self._retry_counts[task_id] = count
        state = await self.get_state(task_id)
        if count <= self._max_retries:
            return await self.transition(
                tenant_id,
                state,
                TaskStatus.HELD,
                note=f"Attempt {count}/{self._max_retries} failed: {error_message}. Held for review.",
            )
        return await self.transition(
            tenant_id,
            state,
            TaskStatus.FAILED,
            note=f"Max retries ({self._max_retries}) exhausted: {error_message}",
        )

    async def evaluate_m5_checkpoint(
        self,
        tenant_id: str,
        *,
        t22_task: CanonicalTaskState | str | None = None,
        t23_task: CanonicalTaskState | str | None = None,
        t24_task: CanonicalTaskState | str | None = None,
        evidence_package: ConsolidatedEvidencePackage | None = None,
        dossier: ActionPreviewDossier | None = None,
        hitl_coordinator: HitlCoordinator | None = None,
        validator: CryptographicValidator | None = None,
    ) -> MilestoneCheckpoint:
        """Evaluate Milestone 5 acceptance checkpoint over T22 -> T23 -> T24.

        Marked COMPLETE only when:
        1. T22, T23, T24 are authoritatively accepted/approved.
        2. T22 evidence package is valid and provenance-recorded.
        3. T23 action preview dossier is traceable to T22.
        4. T24 has valid human cryptographic clearances (Ed25519) from authorized roles,
           binding exact preview content hashes with zero holds/rejections/revisions/expirations.
        """
        async def _resolve_task(task_or_id: CanonicalTaskState | str | None) -> CanonicalTaskState | None:
            if isinstance(task_or_id, str):
                try:
                    return await self.get_state(task_or_id)
                except Exception:
                    return None
            return task_or_id

        task_t22 = await _resolve_task(t22_task)
        task_t23 = await _resolve_task(t23_task)
        task_t24 = await _resolve_task(t24_task)

        blockers: list[str] = []
        is_failed = False
        is_blocked = False
        is_partial = False
        clearance_ids: list[str] = []

        linked_task_ids = [
            task_t22.task_id if task_t22 else "T22",
            task_t23.task_id if task_t23 else "T23",
            task_t24.task_id if task_t24 else "T24",
        ]

        # 1. Verify T22 Task
        if task_t22 is None:
            is_partial = True
            blockers.append("T22 task state missing or uninitialized")
        else:
            if task_t22.status in (TaskStatus.FAILED, TaskStatus.REJECTED):
                is_failed = True
                blockers.append(f"T22 is in failed state '{task_t22.status.value}'")
            elif task_t22.status is TaskStatus.HELD or task_t22.hold_reason or task_t22.prerequisite_locks:
                is_blocked = True
                blockers.append(f"T22 is HELD or has active locks: {task_t22.hold_reason or task_t22.prerequisite_locks}")
            elif task_t22.status is not TaskStatus.COMPLETED:
                is_partial = True
                blockers.append(f"T22 is not COMPLETED (current status: '{task_t22.status.value}')")
            if not task_t22.governance_approved:
                is_blocked = True
                blockers.append("T22 governance approval is unresolved")

        # 2. Verify T23 Task
        if task_t23 is None:
            is_partial = True
            blockers.append("T23 task state missing or uninitialized")
        else:
            if task_t23.status in (TaskStatus.FAILED, TaskStatus.REJECTED):
                is_failed = True
                blockers.append(f"T23 is in failed state '{task_t23.status.value}'")
            elif task_t23.status is TaskStatus.HELD or task_t23.hold_reason or task_t23.prerequisite_locks:
                is_blocked = True
                blockers.append(f"T23 is HELD or has active locks: {task_t23.hold_reason or task_t23.prerequisite_locks}")
            elif task_t23.status is not TaskStatus.COMPLETED:
                is_partial = True
                blockers.append(f"T23 is not COMPLETED (current status: '{task_t23.status.value}')")
            if not task_t23.governance_approved:
                is_blocked = True
                blockers.append("T23 governance approval is unresolved")

        # 3. Verify T24 Task
        if task_t24 is None:
            is_partial = True
            blockers.append("T24 task state missing or uninitialized")
        else:
            if task_t24.status in (TaskStatus.FAILED, TaskStatus.REJECTED):
                is_failed = True
                blockers.append(f"T24 is in failed state '{task_t24.status.value}'")
            elif task_t24.status is TaskStatus.HELD or task_t24.hold_reason or task_t24.prerequisite_locks:
                is_blocked = True
                blockers.append(f"T24 is HELD or has active locks: {task_t24.hold_reason or task_t24.prerequisite_locks}")
            elif task_t24.status is not TaskStatus.APPROVED:
                is_partial = True
                blockers.append(f"T24 is not APPROVED (current status: '{task_t24.status.value}')")
            if not task_t24.governance_approved:
                is_blocked = True
                blockers.append("T24 governance approval is unresolved")

        # 4. Verify T22 Evidence Package
        if evidence_package is None:
            is_blocked = True
            blockers.append("T22 consolidated evidence package is missing")
        else:
            pkg_status = getattr(evidence_package.status, "value", str(evidence_package.status)).lower()
            if pkg_status in ("rejected", "invalid"):
                is_failed = True
                blockers.append(f"T22 evidence package status is '{pkg_status}'")
            elif pkg_status != "validated" and not getattr(evidence_package, "is_valid", True):
                is_blocked = True
                blockers.append(f"T22 evidence package is not validated (status: '{pkg_status}')")
            if evidence_package.tenant_id not in ("default", "global", tenant_id):
                is_blocked = True
                blockers.append(f"T22 evidence package tenant mismatch ({evidence_package.tenant_id} != {tenant_id})")

        # 5. Verify T23 Action Preview Dossier
        if dossier is None or not dossier.previews:
            is_blocked = True
            blockers.append("T23 action preview dossier is missing or empty")
        else:
            if dossier.tenant_id not in ("default", "global", tenant_id):
                is_blocked = True
                blockers.append(f"T23 dossier tenant mismatch ({dossier.tenant_id} != {tenant_id})")
            if evidence_package and dossier.source_package_id and dossier.source_package_id != evidence_package.package_id:
                is_blocked = True
                blockers.append(f"T23 dossier source package '{dossier.source_package_id}' does not match T22 package '{evidence_package.package_id}'")

        # 6. Verify T24 HITL Clearance & Cryptographic Authorization
        if hitl_coordinator is None:
            is_blocked = True
            blockers.append("HITL coordinator missing for clearance verification")
        else:
            if dossier and dossier.previews:
                for preview in dossier.previews:
                    decision = hitl_coordinator.get_decision(preview.preview_id)
                    if decision is None:
                        is_blocked = True
                        blockers.append(f"Preview '{preview.preview_id}' has not been reviewed")
                        continue
                    if not decision.approved or str(decision.decision) != "APPROVE":
                        if str(decision.decision) == "REJECT":
                            is_blocked = True
                            blockers.append(f"Preview '{preview.preview_id}' was REJECTED by human reviewer")
                        elif str(decision.decision) == "REQUEST_REVISION":
                            is_blocked = True
                            blockers.append(f"Preview '{preview.preview_id}' has revision requested: {decision.revision_notes or 'changes requested'}")
                        else:
                            is_blocked = True
                            blockers.append(f"Preview '{preview.preview_id}' is not approved (decision: {decision.decision})")
                        continue

                    if preview.review_status != ReviewStatus.APPROVED:
                        is_blocked = True
                        blockers.append(f"Preview '{preview.preview_id}' review status is {preview.review_status}, expected APPROVED")
                        continue

                    clearance = decision.clearance
                    if not clearance:
                        is_blocked = True
                        blockers.append(f"Signed clearance missing for preview '{preview.preview_id}'")
                        continue
                    if not clearance.is_valid:
                        is_blocked = True
                        blockers.append(f"Clearance for preview '{preview.preview_id}' is marked invalid/revoked")
                        continue

                    if clearance.expires_at is not None and clearance.expires_at < datetime.now(UTC):
                        is_blocked = True
                        blockers.append(f"Clearance for preview '{preview.preview_id}' expired at {clearance.expires_at}")
                        continue

                    if clearance.tenant_id not in ("default", "global", tenant_id):
                        is_blocked = True
                        blockers.append(f"Clearance tenant mismatch for '{preview.preview_id}' ({clearance.tenant_id} != {tenant_id})")
                        continue

                    allowed_roles = CATEGORY_ROLE_PERMISSIONS.get(preview.kind, {"admin"})
                    role_str = clearance.approver_role.lower() if isinstance(clearance.approver_role, str) else str(clearance.approver_role).lower()
                    if role_str not in allowed_roles and "admin" not in role_str:
                        is_blocked = True
                        blockers.append(f"Reviewer role '{clearance.approver_role}' unauthorized to approve '{preview.kind.value}' preview")
                        continue

                    current_hash = compute_preview_hash(preview)
                    if clearance.preview_content_hash != current_hash:
                        is_blocked = True
                        blockers.append(f"Preview content hash mismatch for '{preview.preview_id}' (artifact tampered or mutated)")
                        continue

                    sig = clearance.signature
                    pub_pem = clearance.public_key_pem
                    if not sig or not pub_pem:
                        is_blocked = True
                        blockers.append(f"Missing cryptographic signature or public key for preview '{preview.preview_id}'")
                        continue

                    val = validator or CryptographicValidator(public_key_pem=pub_pem)
                    dec_time_str = clearance.decided_at.isoformat() if hasattr(clearance.decided_at, "isoformat") else str(clearance.decided_at)
                    canon_bytes = canonical_decision_bytes(
                        preview_id=preview.preview_id,
                        decision=clearance.decision.value if hasattr(clearance.decision, "value") else str(clearance.decision),
                        approver=clearance.approver,
                        tenant_id=clearance.tenant_id,
                        preview_content_hash=clearance.preview_content_hash,
                        decided_at=dec_time_str,
                        revision_notes=clearance.revision_notes or "",
                    )
                    if not val.verify(canon_bytes, sig):
                        is_blocked = True
                        blockers.append(f"Cryptographic signature verification failed for preview '{preview.preview_id}' (invalid/forged/replayed)")
                        continue

                    clearance_ids.append(clearance.clearance_id)

        # 7. Derive Final Status
        if is_failed:
            final_status = MilestoneStatus.FAILED
        elif is_blocked:
            final_status = MilestoneStatus.BLOCKED
        elif is_partial:
            final_status = MilestoneStatus.PARTIAL
        else:
            final_status = MilestoneStatus.COMPLETE

        # 8. Construct MilestoneCheckpoint
        checkpoint = MilestoneCheckpoint(
            milestone_id="M5",
            title="HITL Gateway Clearance & Cryptographic Authorization",
            status=final_status,
            tenant_id=tenant_id,
            linked_task_ids=linked_task_ids,
            evidence_package_id=evidence_package.package_id if evidence_package else None,
            dossier_id=dossier.dossier_id if dossier else None,
            clearance_ids=clearance_ids,
            evaluated_at=datetime.now(UTC),
            blockers=blockers,
            metadata={
                "t22_status": task_t22.status.value if task_t22 else None,
                "t23_status": task_t23.status.value if task_t23 else None,
                "t24_status": task_t24.status.value if task_t24 else None,
                "clearance_count": len(clearance_ids),
            },
        )

        # 9. Persist Checkpoint in CTS State and Provenance
        if task_t24 is not None:
            updated_cts_state = dict(task_t24.cts_state)
            updated_cts_state["milestone_m5"] = checkpoint.model_dump(mode="json")
            task_t24 = task_t24.model_copy(update={"cts_state": updated_cts_state})
            await self._repository.save_state(tenant_id, task_t24)

        if self._provenance_recorder:
            await self._provenance_recorder.record(
                tenant_id=tenant_id,
                entity_id="M5",
                activity="milestone_checkpoint_m5",
                agent="cts_milestone_evaluator",
                metadata={
                    "milestone_id": "M5",
                    "status": final_status.value,
                    "blockers": blockers,
                    "clearance_ids": clearance_ids,
                },
            )

        return checkpoint

