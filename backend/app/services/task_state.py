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

    async def evaluate_m6_checkpoint(
        self,
        tenant_id: str,
        *,
        t25_task: CanonicalTaskState | str | None = None,
        t26_task: CanonicalTaskState | str | None = None,
        t27_task: CanonicalTaskState | str | None = None,
        t28_task: CanonicalTaskState | str | None = None,
        t29_task: CanonicalTaskState | str | None = None,
        cms_deployment: Any | None = None,
        paid_deployment: Any | None = None,
        social_deployment: Any | None = None,
        telemetry_readiness: Any | None = None,
    ) -> MilestoneCheckpoint:
        """Evaluate Milestone 6 acceptance checkpoint over T25 + T26 + T27 + T28 + T29.

        Marked COMPLETE only when:
        1. T25 (Outbound Boundary) is authoritatively authorized and active.
        2. T26 (Website/CMS), T27 (Paid Ads), T28 (Social) have completed approved deployments within scope.
        3. T29 (Telemetry Engine) has validated, operational listeners for all active T26-T28 surfaces.
        4. Cross-system tenant and platform scopes match with zero unresolved holds, locks, or failures.
        5. T30 is confirmed eligible through canonical T29 dependency without altering the DAG.
        """
        async def _resolve_task(task_or_id: CanonicalTaskState | str | None) -> CanonicalTaskState | None:
            if isinstance(task_or_id, str):
                try:
                    return await self.get_state(task_or_id)
                except Exception:
                    return None
            return task_or_id

        def _get_task_tenant(t: CanonicalTaskState | None) -> str | None:
            if not t:
                return None
            return getattr(t, "tenant_id", None) or t.cts_state.get("tenant_id")

        task_t25 = await _resolve_task(t25_task)
        task_t26 = await _resolve_task(t26_task)
        task_t27 = await _resolve_task(t27_task)
        task_t28 = await _resolve_task(t28_task)
        task_t29 = await _resolve_task(t29_task)

        blockers: list[str] = []
        is_failed = False
        is_blocked = False
        is_partial = False

        linked_task_ids = [
            task_t25.task_id if task_t25 else "T25",
            task_t26.task_id if task_t26 else "T26",
            task_t27.task_id if task_t27 else "T27",
            task_t28.task_id if task_t28 else "T28",
            task_t29.task_id if task_t29 else "T29",
        ]

        # 1. Verify T25: Outbound Boundary Authorization
        if task_t25 is None:
            is_partial = True
            blockers.append("T25 task state missing or uninitialized")
        else:
            if task_t25.status in (TaskStatus.FAILED, TaskStatus.REJECTED):
                is_failed = True
                blockers.append(f"T25 is in failed state '{task_t25.status.value}'")
            elif task_t25.status is TaskStatus.HELD or task_t25.hold_reason or task_t25.prerequisite_locks:
                is_blocked = True
                blockers.append(f"T25 is HELD or has active locks: {task_t25.hold_reason or task_t25.prerequisite_locks}")
            elif task_t25.status not in (TaskStatus.COMPLETED, TaskStatus.APPROVED, TaskStatus.DISPATCHED):
                is_partial = True
                blockers.append(f"T25 is not completed/approved (current status: '{task_t25.status.value}')")
            if not task_t25.governance_approved:
                is_blocked = True
                blockers.append("T25 governance approval is unresolved")
            t25_tenant = _get_task_tenant(task_t25)
            if t25_tenant and t25_tenant not in ("default", "global", tenant_id):
                is_blocked = True
                blockers.append(f"T25 tenant mismatch ({t25_tenant} != {tenant_id})")

        # 2. Verify T26: Website & CMS Deployment
        if task_t26 is None:
            is_partial = True
            blockers.append("T26 task state missing or uninitialized")
        else:
            if task_t26.status in (TaskStatus.FAILED, TaskStatus.REJECTED):
                is_failed = True
                blockers.append(f"T26 is in failed state '{task_t26.status.value}'")
            elif task_t26.status is TaskStatus.HELD or task_t26.hold_reason or task_t26.prerequisite_locks:
                is_blocked = True
                blockers.append(f"T26 is HELD or has active locks: {task_t26.hold_reason or task_t26.prerequisite_locks}")
            elif task_t26.status not in (TaskStatus.COMPLETED, TaskStatus.DISPATCHED):
                is_partial = True
                blockers.append(f"T26 is not completed (current status: '{task_t26.status.value}')")
            if not task_t26.governance_approved:
                is_blocked = True
                blockers.append("T26 governance approval is unresolved")
            t26_tenant = _get_task_tenant(task_t26)
            if t26_tenant and t26_tenant not in ("default", "global", tenant_id):
                is_blocked = True
                blockers.append(f"T26 tenant mismatch ({t26_tenant} != {tenant_id})")

        cms_dep = cms_deployment or (task_t26.cts_state.get("deployment") if task_t26 else None)
        if cms_dep is None and task_t26 and task_t26.status == TaskStatus.COMPLETED and not task_t26.cts_state:
            is_blocked = True
            blockers.append("T26 CMS deployment record is missing")
        elif cms_dep:
            dep_status = cms_dep.get("status") if isinstance(cms_dep, dict) else getattr(cms_dep, "status", None)
            dep_code = str(cms_dep.get("status_code", "200") if isinstance(cms_dep, dict) else getattr(cms_dep, "status_code", "200"))
            if dep_status in ("failed", "rejected") or dep_code.startswith("5"):
                is_failed = True
                blockers.append(f"T26 CMS deployment failed: status='{dep_status}', code='{dep_code}'")
            elif dep_status not in ("published", "active", "deployed", "completed") and dep_code not in ("200", "201", "204"):
                is_blocked = True
                blockers.append(f"T26 CMS deployment not published: status='{dep_status}'")
            dep_tenant = cms_dep.get("tenant_id") if isinstance(cms_dep, dict) else getattr(cms_dep, "tenant_id", None)
            if dep_tenant and dep_tenant not in ("default", "global", tenant_id):
                is_blocked = True
                blockers.append(f"T26 CMS deployment tenant mismatch ({dep_tenant} != {tenant_id})")

        # 3. Verify T27: Paid Media Campaigns
        if task_t27 is None:
            is_partial = True
            blockers.append("T27 task state missing or uninitialized")
        else:
            if task_t27.status in (TaskStatus.FAILED, TaskStatus.REJECTED):
                is_failed = True
                blockers.append(f"T27 is in failed state '{task_t27.status.value}'")
            elif task_t27.status is TaskStatus.HELD or task_t27.hold_reason or task_t27.prerequisite_locks:
                is_blocked = True
                blockers.append(f"T27 is HELD or has active locks: {task_t27.hold_reason or task_t27.prerequisite_locks}")
            elif task_t27.status not in (TaskStatus.COMPLETED, TaskStatus.DISPATCHED):
                is_partial = True
                blockers.append(f"T27 is not completed (current status: '{task_t27.status.value}')")
            if not task_t27.governance_approved:
                is_blocked = True
                blockers.append("T27 governance approval is unresolved")
            t27_tenant = _get_task_tenant(task_t27)
            if t27_tenant and t27_tenant not in ("default", "global", tenant_id):
                is_blocked = True
                blockers.append(f"T27 tenant mismatch ({t27_tenant} != {tenant_id})")

        paid_dep = paid_deployment or (
            task_t27.cts_state.get("paid_campaign") or task_t27.cts_state.get("deployment")
            if task_t27
            else None
        )
        if paid_dep is None and task_t27 and task_t27.status == TaskStatus.COMPLETED and not task_t27.cts_state:
            is_blocked = True
            blockers.append("T27 paid campaign deployment record is missing")
        elif paid_dep:
            dep_status = paid_dep.get("status") if isinstance(paid_dep, dict) else getattr(paid_dep, "status", None)
            dep_channel = str(paid_dep.get("channel") if isinstance(paid_dep, dict) else getattr(paid_dep, "channel", "")).lower()
            if dep_status in ("failed", "rejected"):
                is_failed = True
                blockers.append(f"T27 paid campaign failed: status='{dep_status}'")
            if dep_channel and dep_channel not in ("meta", "google", "tiktok", "linkedin"):
                is_blocked = True
                blockers.append(f"T27 platform '{dep_channel}' is not a permitted canonical ad platform")
            if dep_channel == "linkedin":
                details = paid_dep.get("details", {}) if isinstance(paid_dep, dict) else getattr(paid_dep, "details", {})
                is_auth = details.get("authorized", False) or (task_t27 and task_t27.cts_state.get("linkedin_authorized", False))
                if not is_auth:
                    is_blocked = True
                    blockers.append("T27 platform 'linkedin' was deployed without explicit authorization")
            details = paid_dep.get("details", {}) if isinstance(paid_dep, dict) else getattr(paid_dep, "details", {})
            applied_budget = paid_dep.get("applied_budget") if isinstance(paid_dep, dict) else getattr(paid_dep, "applied_budget", None)
            approved_budget = (
                paid_dep.get("approved_budget")
                if isinstance(paid_dep, dict)
                else getattr(paid_dep, "approved_budget", None)
            )
            if approved_budget is None and isinstance(details, dict):
                approved_budget = details.get("approved_budget")
            if applied_budget is not None and approved_budget is not None and float(applied_budget) > float(approved_budget):
                is_blocked = True
                blockers.append(f"T27 spend escalation: applied {applied_budget} > approved {approved_budget}")

            applied_bid = paid_dep.get("applied_bid") if isinstance(paid_dep, dict) else getattr(paid_dep, "applied_bid", None)
            approved_bid = (
                paid_dep.get("approved_bid")
                if isinstance(paid_dep, dict)
                else getattr(paid_dep, "approved_bid", None)
            )
            if approved_bid is None and isinstance(details, dict):
                approved_bid = details.get("approved_bid")
            if applied_bid is not None and approved_bid is not None and float(applied_bid) > float(approved_bid):
                is_blocked = True
                blockers.append(f"T27 bid escalation: applied {applied_bid} > approved {approved_bid}")
            dep_tenant = paid_dep.get("tenant_id") if isinstance(paid_dep, dict) else getattr(paid_dep, "tenant_id", None)
            if dep_tenant and dep_tenant not in ("default", "global", tenant_id):
                is_blocked = True
                blockers.append(f"T27 paid campaign tenant mismatch ({dep_tenant} != {tenant_id})")

        # 4. Verify T28: Social Posts & Assets
        if task_t28 is None:
            is_partial = True
            blockers.append("T28 task state missing or uninitialized")
        else:
            if task_t28.status in (TaskStatus.FAILED, TaskStatus.REJECTED):
                is_failed = True
                blockers.append(f"T28 is in failed state '{task_t28.status.value}'")
            elif task_t28.status is TaskStatus.HELD or task_t28.hold_reason or task_t28.prerequisite_locks:
                is_blocked = True
                blockers.append(f"T28 is HELD or has active locks: {task_t28.hold_reason or task_t28.prerequisite_locks}")
            elif task_t28.status not in (TaskStatus.COMPLETED, TaskStatus.DISPATCHED):
                is_partial = True
                blockers.append(f"T28 is not completed (current status: '{task_t28.status.value}')")
            if not task_t28.governance_approved:
                is_blocked = True
                blockers.append("T28 governance approval is unresolved")
            t28_tenant = _get_task_tenant(task_t28)
            if t28_tenant and t28_tenant not in ("default", "global", tenant_id):
                is_blocked = True
                blockers.append(f"T28 tenant mismatch ({t28_tenant} != {tenant_id})")

        social_dep = social_deployment or (
            task_t28.cts_state.get("social_post") or task_t28.cts_state.get("deployment")
            if task_t28
            else None
        )
        if social_dep is None and task_t28 and task_t28.status == TaskStatus.COMPLETED and not task_t28.cts_state:
            is_blocked = True
            blockers.append("T28 social post deployment record is missing")
        elif social_dep:
            dep_status = social_dep.get("status") if isinstance(social_dep, dict) else getattr(social_dep, "status", None)
            dep_channel = str(social_dep.get("channel") if isinstance(social_dep, dict) else getattr(social_dep, "channel", "")).lower()
            if dep_status in ("failed", "rejected"):
                is_failed = True
                blockers.append(f"T28 social post failed: status='{dep_status}'")
            if dep_channel and dep_channel not in ("instagram", "x", "youtube", "tiktok"):
                is_blocked = True
                blockers.append(f"T28 channel '{dep_channel}' is not a permitted canonical social channel")
            social_details = social_dep.get("details", {}) if isinstance(social_dep, dict) else getattr(social_dep, "details", {})
            if dep_channel == "tiktok":
                is_auth = social_details.get("authorized", False) or (task_t28 and task_t28.cts_state.get("tiktok_authorized", False))
                if not is_auth:
                    is_blocked = True
                    blockers.append("T28 channel 'tiktok' was published without explicit authorization")
            if (
                (isinstance(social_dep, dict) and social_dep.get("tampered"))
                or getattr(social_dep, "tampered", False)
                or (isinstance(social_details, dict) and social_details.get("tampered"))
            ):
                is_blocked = True
                blockers.append("T28 social post copy or media asset was tampered")
            dep_tenant = social_dep.get("tenant_id") if isinstance(social_dep, dict) else getattr(social_dep, "tenant_id", None)
            if dep_tenant and dep_tenant not in ("default", "global", tenant_id):
                is_blocked = True
                blockers.append(f"T28 social post tenant mismatch ({dep_tenant} != {tenant_id})")

        # 5. Verify T29: Omnichannel Telemetry Engine Readiness
        if task_t29 is None:
            is_partial = True
            blockers.append("T29 task state missing or uninitialized")
        else:
            if task_t29.status in (TaskStatus.FAILED, TaskStatus.REJECTED):
                is_failed = True
                blockers.append(f"T29 is in failed state '{task_t29.status.value}'")
            elif task_t29.status is TaskStatus.HELD or task_t29.hold_reason or task_t29.prerequisite_locks:
                is_blocked = True
                blockers.append(f"T29 is HELD or has active locks: {task_t29.hold_reason or task_t29.prerequisite_locks}")
            elif task_t29.status not in (TaskStatus.COMPLETED, TaskStatus.APPROVED, TaskStatus.DISPATCHED):
                is_partial = True
                blockers.append(f"T29 is not completed (current status: '{task_t29.status.value}')")
            if not task_t29.governance_approved:
                is_blocked = True
                blockers.append("T29 governance approval is unresolved")
            t29_tenant = _get_task_tenant(task_t29)
            if t29_tenant and t29_tenant not in ("default", "global", tenant_id):
                is_blocked = True
                blockers.append(f"T29 tenant mismatch ({t29_tenant} != {tenant_id})")

        t_ready = telemetry_readiness or (task_t29.cts_state.get("telemetry_engine") if task_t29 else None)
        if t_ready is None and task_t29 and task_t29.status == TaskStatus.COMPLETED and not task_t29.cts_state:
            is_blocked = True
            blockers.append("T29 telemetry readiness record is missing")
        elif t_ready:
            is_ready_flag = t_ready.get("is_ready") if isinstance(t_ready, dict) else getattr(t_ready, "is_ready", False)
            if not is_ready_flag:
                is_blocked = True
                blockers.append("T29 telemetry engine is not ready (listener or probe failures)")
            b_reasons = t_ready.get("blocked_reasons", []) if isinstance(t_ready, dict) else getattr(t_ready, "blocked_reasons", [])
            if b_reasons:
                is_blocked = True
                blockers.extend([f"T29 probe failure: {r}" for r in b_reasons])
            ready_tenant = t_ready.get("tenant_id") if isinstance(t_ready, dict) else getattr(t_ready, "tenant_id", None)
            if ready_tenant and ready_tenant not in ("default", "global", tenant_id):
                is_blocked = True
                blockers.append(f"T29 telemetry tenant mismatch ({ready_tenant} != {tenant_id})")

        # 6. Derive Final Status
        if is_failed:
            final_status = MilestoneStatus.FAILED
        elif is_blocked:
            final_status = MilestoneStatus.BLOCKED
        elif is_partial:
            final_status = MilestoneStatus.PARTIAL
        else:
            final_status = MilestoneStatus.COMPLETE

        t30_eligible = (final_status == MilestoneStatus.COMPLETE)

        # 7. Construct MilestoneCheckpoint
        active_surfaces_count = 0
        if t_ready:
            surfaces = t_ready.get("active_surfaces", []) if isinstance(t_ready, dict) else getattr(t_ready, "active_surfaces", [])
            active_surfaces_count = len(surfaces)

        checkpoint = MilestoneCheckpoint(
            milestone_id="M6",
            title="Outbound Actuation, Telemetry & Omnichannel Go-Live",
            status=final_status,
            tenant_id=tenant_id,
            linked_task_ids=linked_task_ids,
            evaluated_at=datetime.now(UTC),
            blockers=blockers,
            metadata={
                "t25_status": task_t25.status.value if task_t25 else None,
                "t26_status": task_t26.status.value if task_t26 else None,
                "t27_status": task_t27.status.value if task_t27 else None,
                "t28_status": task_t28.status.value if task_t28 else None,
                "t29_status": task_t29.status.value if task_t29 else None,
                "t30_eligible": t30_eligible,
                "active_surfaces_count": active_surfaces_count,
            },
        )

        # 8. Persist Checkpoint in CTS State and Provenance
        if task_t29 is not None:
            updated_cts_state = dict(task_t29.cts_state)
            updated_cts_state["milestone_m6"] = checkpoint.model_dump(mode="json")
            task_t29 = task_t29.model_copy(update={"cts_state": updated_cts_state})
            await self._repository.save_state(tenant_id, task_t29)

        if self._provenance_recorder:
            await self._provenance_recorder.record(
                tenant_id=tenant_id,
                entity_id="M6",
                activity="milestone_checkpoint_m6",
                agent="cts_milestone_evaluator",
                metadata={
                    "milestone_id": "M6",
                    "status": final_status.value,
                    "t30_eligible": t30_eligible,
                    "blockers": blockers,
                    "linked_task_ids": linked_task_ids,
                },
            )

        return checkpoint


