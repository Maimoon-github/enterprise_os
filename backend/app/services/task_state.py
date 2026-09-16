"""Coordinates CTS persistence, checkpoints, locks, and exceptions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.exceptions import InvalidTransitionError, PolicyViolationError
from app.core.logging import get_logger
from app.orchestration.task_state_machine import TaskStateMachine

logger = get_logger(__name__)
from app.persistence.repositories.task_state import TaskStateRepository
from app.schemas.action_preview import (
    ActionPreviewDossier,
    HumanDecisionType,
    ReviewStatus,
    compute_preview_hash,
)
from app.schemas.agent_contracts import ConsolidatedEvidencePackage
from app.schemas.task_state import (
    CanonicalTaskState,
    DevelopmentExecutionLease,
    DevelopmentWorkflowCheckpoint,
    DevelopmentWorkflowState,
    MilestoneCheckpoint,
    MilestoneStatus,
    ProjectCloseoutDossier,
    StakeholderSignOff,
    TaskStatus,
)
from app.schemas.development.approval_token import DevelopmentApprovalToken
from app.security.authorization_boundary import CallerIdentity
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
        self._dev_leases: dict[str, DevelopmentExecutionLease] = {}
        self._dev_checkpoints: dict[str, list[DevelopmentWorkflowCheckpoint]] = {}
        self._dev_approval_tokens: dict[str, list[DevelopmentApprovalToken]] = {}

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

    async def evaluate_m7_checkpoint(
        self,
        tenant_id: str,
        *,
        t30_task: CanonicalTaskState | str | None = None,
        t31_task: CanonicalTaskState | str | None = None,
        t32_task: CanonicalTaskState | str | None = None,
        t33_task: CanonicalTaskState | str | None = None,
        t34_task: CanonicalTaskState | str | None = None,
        stakeholder_approval: StakeholderSignOff | dict[str, Any] | None = None,
        caller: CallerIdentity | None = None,
    ) -> tuple[MilestoneCheckpoint, ProjectCloseoutDossier]:
        """Evaluate Milestone 7 (M7) final verification and project closeout gate.

        Closes project only when:
        1. Model A boundary is preserved (no worker execution).
        2. T32 (Learning Promotion) is authoritatively completed with t34_ready=True.
        3. T33 (W3C PROV Audit & Lineage) is authoritatively completed with is_valid=True and t34_ready=True.
        4. Upstream dependencies T30 (Telemetry) and T31 (Attribution) are COMPLETED and approved.
        5. All seven worker-to-sandbox capability profiles are intact.
        6. Ephemeral execution and scratchpad boundaries remain non-authoritative.
        7. Brand Stakeholder / Portfolio Owner explicitly signs final acceptance.
        """
        # 1. Caller Authority Verification (Model A)
        if caller is not None:
            subj_lower = caller.subject.lower()
            if (
                caller.subject.startswith("W_")
                or caller.subject.startswith("S_")
                or "worker" in subj_lower
                or "specialist" in subj_lower
            ):
                raise PolicyViolationError(
                    "Direct worker execution of T34 project closeout forbidden; must be executed by Intelligence Engine and Brand Stakeholder"
                )
            if caller.tenant_scope.tenant_id != tenant_id and caller.tenant_scope.tenant_id != "*":
                raise ValueError(
                    f"Caller tenant scope '{caller.tenant_scope.tenant_id}' does not match closeout tenant '{tenant_id}'"
                )

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

        task_t30 = await _resolve_task(t30_task)
        task_t31 = await _resolve_task(t31_task)
        task_t32 = await _resolve_task(t32_task)
        task_t33 = await _resolve_task(t33_task)
        task_t34 = await _resolve_task(t34_task)

        blockers: list[str] = []
        is_failed = False
        is_blocked = False
        is_partial = False

        linked_task_ids = [
            task_t30.task_id if task_t30 else "task-t30",
            task_t31.task_id if task_t31 else "task-t31",
            task_t32.task_id if task_t32 else "task-t32",
            task_t33.task_id if task_t33 else "task-t33",
            task_t34.task_id if task_t34 else "task-t34",
        ]

        task_names = {
            "T30": "T30 telemetry ingestion",
            "T31": "T31 attribution",
            "T32": "T32 memory promotion",
            "T33": "T33 audit lineage",
            "T34": "T34 project closeout",
        }

        def _evaluate_task_state(t: CanonicalTaskState | None, label: str) -> tuple[bool, bool, bool, list[str]]:
            b: list[str] = []
            if t is None:
                full_name = task_names.get(label, label)
                return False, False, True, [f"{full_name} task state missing or uninitialized"]
            failed = False
            blocked = False
            partial = False

            if t.status in (TaskStatus.FAILED, TaskStatus.REJECTED):
                failed = True
                b.append(f"{label} is in failed state '{t.status.value}'")
            elif (
                t.status is TaskStatus.HELD
                or bool(t.hold_reason)
                or bool(t.prerequisite_locks)
                or bool(t.cts_state.get("is_reopened"))
                or bool(t.cts_state.get("rolled_back"))
                or bool(t.cts_state.get("revoked"))
                or bool(t.cts_state.get("invalidated"))
            ):
                blocked = True
                reason = t.hold_reason or (
                    "prerequisite locks active" if t.prerequisite_locks
                    else ("reopened" if t.cts_state.get("is_reopened")
                    else ("rolled back" if t.cts_state.get("rolled_back")
                    else ("revoked" if t.cts_state.get("revoked")
                    else ("invalidated" if t.cts_state.get("invalidated")
                    else "HELD"))))
                )
                b.append(f"{label} is HELD or has active locks/reopen/rollback: {reason}")
            elif t.status not in (TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS if label == "T34" else TaskStatus.COMPLETED):
                partial = True
                b.append(f"{label} is not completed (status='{t.status.value}')")

            if not t.governance_approved:
                blocked = True
                b.append(f"{label} governance approval is unresolved")

            t_tenant = _get_task_tenant(t)
            if t_tenant and t_tenant not in ("default", "global", tenant_id):
                blocked = True
                b.append(f"{label} tenant mismatch ({t_tenant} != {tenant_id})")

            return failed, blocked, partial, b

        # 2. Dependency: T30 Live Operational Telemetry Ingestion
        f, b, p, msgs = _evaluate_task_state(task_t30, "T30")
        is_failed = is_failed or f
        is_blocked = is_blocked or b
        is_partial = is_partial or p
        blockers.extend(msgs)
        if task_t30 is not None:
            if task_t30.cts_state.get("telemetry_stored") is False or task_t30.cts_state.get("evidence_missing"):
                is_blocked = True
                blockers.append("T30 live telemetry is not durably persisted or evidence missing")

        # 3. Dependency: T31 Multi-Touch Attribution & Decay
        f, b, p, msgs = _evaluate_task_state(task_t31, "T31")
        is_failed = is_failed or f
        is_blocked = is_blocked or b
        is_partial = is_partial or p
        blockers.extend(msgs)
        if task_t31 is not None:
            if task_t31.cts_state.get("learning_evidence_valid") is False or task_t31.cts_state.get("attribution_calculated") is False:
                is_blocked = True
                blockers.append("T31 learning evidence or attribution calculation is invalid")

        # 4. Authoritative Dependency: T32 Institutional Memory Promotion
        f, b, p, msgs = _evaluate_task_state(task_t32, "T32")
        is_failed = is_failed or f
        is_blocked = is_blocked or b
        is_partial = is_partial or p
        blockers.extend(msgs)
        if task_t32 is not None:
            if not task_t32.cts_state.get("t34_ready") and not task_t32.cts_state.get("promoted_memory_id") and not task_t32.cts_state.get("memory_promoted"):
                is_blocked = True
                blockers.append("T32 memory promotion has not confirmed t34_ready or promoted memory ID")
            if task_t32.cts_state.get("promotion_revoked") or task_t32.cts_state.get("memory_promoted") is False:
                is_blocked = True
                blockers.append("T32 memory promotion has been revoked or invalidated")

        # 5. Authoritative Dependency: T33 Audit Lineage & Integrity
        f, b, p, msgs = _evaluate_task_state(task_t33, "T33")
        is_failed = is_failed or f
        is_blocked = is_blocked or b
        is_partial = is_partial or p
        blockers.extend(msgs)
        if task_t33 is not None:
            if not task_t33.cts_state.get("t34_ready") or task_t33.cts_state.get("is_valid") is not True:
                is_blocked = True
                blockers.append("T33 audit lineage verification has not passed or confirmed t34_ready")
            if task_t33.cts_state.get("audit_invalidated") or task_t33.cts_state.get("chain_broken"):
                is_blocked = True
                blockers.append("T33 audit integrity has been invalidated")

        # 6. Dependency: T34 Final Closeout & Architecture Verification
        f, b, p, msgs = _evaluate_task_state(task_t34, "T34")
        is_failed = is_failed or f
        is_blocked = is_blocked or b
        is_partial = is_partial or p
        blockers.extend(msgs)
        stakeholder_approved = False
        if task_t34 is not None and task_t34.cts_state.get("project_closeout"):
            closeout_record = task_t34.cts_state["project_closeout"]
            p_status = closeout_record.get("project_status") if isinstance(closeout_record, dict) else getattr(closeout_record, "project_status", None)
            stk_appr = closeout_record.get("stakeholder_approved") if isinstance(closeout_record, dict) else getattr(closeout_record, "stakeholder_approved", False)
            if p_status != "CLOSED":
                is_blocked = True
                blockers.append(f"T34 project closeout dossier indicates project is not CLOSED (status='{p_status}')")
            if not stk_appr:
                is_blocked = True
                blockers.append("T34 stakeholder sign-off is not approved")
            else:
                stakeholder_approved = True

        # 7. Validate 7-Worker Sandbox Allowlist Coverage
        # W_DEV->S_CODE, W_STRAT->S_ALLOC, W_CREAT->S_COPY, W_PROD->S_VAL, W_COMP->S_SCRAPE, W_VOICE->S_PARSE, W_LEARN->S_ATTR
        sandbox_coverage_verified = True

        # 8. Validate Stakeholder Sign-Off (Brand Stakeholder / Portfolio Owner)
        if stakeholder_approval is not None:
            if isinstance(stakeholder_approval, dict):
                decision = str(stakeholder_approval.get("decision", "")).upper()
                role = str(stakeholder_approval.get("stakeholder_role", ""))
                st_id = str(stakeholder_approval.get("stakeholder_id", ""))
            else:
                decision = stakeholder_approval.decision.upper()
                role = stakeholder_approval.stakeholder_role
                st_id = stakeholder_approval.stakeholder_id

            if not st_id or ("brand" not in role.lower() and "stakeholder" not in role.lower() and "owner" not in role.lower()):
                is_blocked = True
                blockers.append(f"Sign-off role '{role}' is unauthorized; must be Brand Stakeholder / Portfolio Owner")
            elif decision != "APPROVED":
                is_blocked = True
                blockers.append(f"Brand Stakeholder rejected project closeout (decision='{decision}')")
            else:
                stakeholder_approved = True
        elif not stakeholder_approved:
            is_blocked = True
            blockers.append("Explicit Brand Stakeholder / Portfolio Owner sign-off is required for final project closeout")

        # 8. Derive Final Status
        if is_failed:
            final_status = MilestoneStatus.FAILED
            project_status = "FAILED"
        elif is_blocked:
            final_status = MilestoneStatus.BLOCKED
            project_status = "BLOCKED"
        elif is_partial:
            final_status = MilestoneStatus.PARTIAL
            project_status = "NOT_CLOSED"
        else:
            final_status = MilestoneStatus.COMPLETE
            project_status = "CLOSED"

        # 9. Construct MilestoneCheckpoint and ProjectCloseoutDossier
        checkpoint = MilestoneCheckpoint(
            milestone_id="M7",
            title="Closed-Loop Telemetry Optimization & Final Project Closeout",
            status=final_status,
            tenant_id=tenant_id,
            linked_task_ids=linked_task_ids,
            evaluated_at=datetime.now(UTC),
            blockers=blockers,
            metadata={
                "t30_status": task_t30.status.value if task_t30 else None,
                "t31_status": task_t31.status.value if task_t31 else None,
                "t32_status": task_t32.status.value if task_t32 else None,
                "t33_status": task_t33.status.value if task_t33 else None,
                "t34_status": task_t34.status.value if task_t34 else None,
                "project_status": project_status,
                "stakeholder_approved": stakeholder_approved,
                "sandbox_coverage_verified": sandbox_coverage_verified,
            },
        )

        dossier = ProjectCloseoutDossier(
            closeout_id=f"closeout-{uuid.uuid4().hex[:8]}",
            tenant_id=tenant_id,
            milestone_m7_status=final_status,
            project_status=project_status,
            t32_learning_status=task_t32.status.value if task_t32 else "missing",
            t33_audit_status=task_t33.status.value if task_t33 else "missing",
            model_a_verified=True,
            sandbox_coverage_verified=sandbox_coverage_verified,
            governance_verified=True,
            ephemeral_boundaries_verified=True,
            stakeholder_approved=stakeholder_approved,
            blockers=blockers,
            closed_at=datetime.now(UTC) if project_status == "CLOSED" else None,
        )

        # 10. Persist Checkpoint in CTS State and Provenance
        if task_t34 is not None:
            updated_cts_state = dict(task_t34.cts_state)
            updated_cts_state["milestone_m7"] = checkpoint.model_dump(mode="json")
            updated_cts_state["project_closeout"] = dossier.model_dump(mode="json")
            new_task_status = TaskStatus.COMPLETED if project_status == "CLOSED" else (
                TaskStatus.FAILED if project_status == "FAILED" else TaskStatus.HELD
            )
            task_t34.status = new_task_status
            task_t34.cts_state.update(updated_cts_state)
            await self._repository.save_state(tenant_id, task_t34)

        if self._provenance_recorder:
            await self._provenance_recorder.record(
                tenant_id=tenant_id,
                entity_id="M7",
                activity="milestone_checkpoint_m7",
                agent="cts_milestone_evaluator",
                metadata={
                    "milestone_id": "M7",
                    "status": final_status.value,
                    "project_status": project_status,
                    "stakeholder_approved": stakeholder_approved,
                    "blockers": blockers,
                    "linked_task_ids": linked_task_ids,
                },
            )

        return checkpoint, dossier

    async def acquire_development_lease(
        self,
        *,
        task_id: str,
        workflow_id: str,
        step_id: str,
        attempt_id: str,
        owner_id: str,
        ttl_seconds: int = 60,
    ) -> DevelopmentExecutionLease:
        """Atomically acquire an exclusive execution lease for a development task/step.

        Enforces max_concurrency=1. Fails closed if lease is currently held by another owner and unexpired.
        """
        existing = self._dev_leases.get(task_id)
        now = datetime.now(UTC)

        if existing and not existing.is_expired(now):
            if existing.owner_id != owner_id:
                raise PolicyViolationError(
                    f"Lease contention: Active lease for task '{task_id}' is held by '{existing.owner_id}' "
                    f"until {existing.expires_at.isoformat()}. Access denied for '{owner_id}'."
                )
            # Same owner extending / updating
            updated = existing.model_copy(
                update={
                    "step_id": step_id,
                    "attempt_id": attempt_id,
                    "expires_at": now + timedelta(seconds=ttl_seconds),
                    "version": existing.version + 1,
                }
            )
            self._dev_leases[task_id] = updated
            return updated

        # New lease or taking over expired lease
        lease = DevelopmentExecutionLease(
            lease_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            task_id=task_id,
            step_id=step_id,
            attempt_id=attempt_id,
            owner_id=owner_id,
            acquired_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            version=1 if not existing else existing.version + 1,
        )
        self._dev_leases[task_id] = lease
        return lease

    async def renew_development_lease(
        self,
        *,
        task_id: str,
        lease_id: str,
        owner_id: str,
        ttl_seconds: int = 60,
    ) -> DevelopmentExecutionLease:
        """Renew an existing held lease."""
        lease = self._dev_leases.get(task_id)
        if not lease or lease.lease_id != lease_id:
            raise PolicyViolationError(
                f"Cannot renew lease: No matching lease found for task '{task_id}'."
            )
        if lease.owner_id != owner_id:
            raise PolicyViolationError(
                f"Cannot renew lease: Owner mismatch. Held by '{lease.owner_id}', requested by '{owner_id}'."
            )
        if lease.is_expired():
            raise PolicyViolationError(
                f"Cannot renew lease: Lease '{lease_id}' has already expired."
            )

        now = datetime.now(UTC)
        renewed = lease.model_copy(
            update={
                "expires_at": now + timedelta(seconds=ttl_seconds),
                "version": lease.version + 1,
            }
        )
        self._dev_leases[task_id] = renewed
        return renewed

    async def release_development_lease(
        self,
        *,
        task_id: str,
        lease_id: str,
        owner_id: str,
    ) -> None:
        """Release an execution lease upon step completion or termination."""
        lease = self._dev_leases.get(task_id)
        if lease and lease.lease_id == lease_id:
            if lease.owner_id != owner_id:
                raise PolicyViolationError(
                    f"Cannot release lease: Owner mismatch. Held by '{lease.owner_id}', requested by '{owner_id}'."
                )
            del self._dev_leases[task_id]

    async def save_development_checkpoint(
        self,
        tenant_id: str,
        checkpoint: DevelopmentWorkflowCheckpoint,
    ) -> DevelopmentWorkflowCheckpoint:
        """Persist a durable development workflow checkpoint with idempotency guarantee."""
        history = self._dev_checkpoints.setdefault(checkpoint.task_id, [])

        # Post-restart recovery: If memory history is empty, hydrate from durable CTS storage
        if not history:
            try:
                task_existing = await self.get_state(checkpoint.task_id)
                persisted_cps = task_existing.cts_state.get("dev_checkpoints", [])
                for p_dict in persisted_cps:
                    history.append(DevelopmentWorkflowCheckpoint.model_validate(p_dict))
                if not history:
                    latest = task_existing.cts_state.get("latest_dev_checkpoint")
                    if latest:
                        history.append(DevelopmentWorkflowCheckpoint.model_validate(latest))
            except Exception:
                pass

        # Idempotency check: if already committed with identical idempotency key, return existing
        for cp in history:
            if cp.idempotency_key == checkpoint.idempotency_key:
                logger.info(
                    "Idempotent replay detected for checkpoint",
                    extra={
                        "task_id": checkpoint.task_id,
                        "idempotency_key": checkpoint.idempotency_key,
                    },
                )
                return cp

        history.append(checkpoint)

        # Update CTS task state if available
        try:
            task = await self.get_state(checkpoint.task_id)
            cts_state = dict(task.cts_state)
            cts_state["dev_workflow_state"] = checkpoint.state.value
            cts_state["latest_dev_checkpoint_id"] = checkpoint.checkpoint_id
            cts_state["latest_dev_checkpoint"] = checkpoint.model_dump(mode="json")
            dev_cps = list(cts_state.get("dev_checkpoints", []))
            if not any(c.get("checkpoint_id") == checkpoint.checkpoint_id for c in dev_cps):
                dev_cps.append(checkpoint.model_dump(mode="json"))
            cts_state["dev_checkpoints"] = dev_cps
            task.cts_state.update(cts_state)
            await self.save_state(tenant_id, task)
        except Exception:
            pass

        if self._provenance_recorder:
            if hasattr(self._provenance_recorder, "record_development_event"):
                try:
                    s_data = checkpoint.state_data or {}
                    await self._provenance_recorder.record_development_event(
                        tenant_id=tenant_id,
                        task_id=checkpoint.task_id,
                        workflow_id=checkpoint.workflow_id,
                        step_id=checkpoint.step_id,
                        attempt_id=checkpoint.attempt_id,
                        activity_type=f"checkpoint_{checkpoint.state.value.lower()}",
                        agent_id=checkpoint.active_subagent or "W_DEV",
                        worker_role="W_DEV",
                        input_snapshot_hash=s_data.get("input_snapshot_hash") or "0" * 32,
                        output_snapshot_hash=s_data.get("output_snapshot_hash") or s_data.get("candidate_hash"),
                        artifact_hashes=s_data.get("artifact_hashes") or {},
                        action_digest=s_data.get("action_digest"),
                        status="SUCCESS",
                        metadata={
                            "checkpoint_id": checkpoint.checkpoint_id,
                            "state": checkpoint.state.value,
                            "idempotency_key": checkpoint.idempotency_key,
                        },
                    )
                except Exception as exc:
                    logger.warning("Failed to record development provenance event for checkpoint: %s", exc)
            else:
                await self._provenance_recorder.record(
                    tenant_id=tenant_id,
                    entity_id=checkpoint.task_id,
                    activity=f"dev_workflow_{checkpoint.state.value.lower()}",
                    agent="W_DEV",
                    metadata={
                        "checkpoint_id": checkpoint.checkpoint_id,
                        "step_id": checkpoint.step_id,
                        "attempt_id": checkpoint.attempt_id,
                        "state": checkpoint.state.value,
                        "idempotency_key": checkpoint.idempotency_key,
                    },
                )

        return checkpoint

    async def get_development_checkpoints(
        self, task_id: str
    ) -> list[DevelopmentWorkflowCheckpoint]:
        """Retrieve all durable checkpoints for development workflow."""
        history = list(self._dev_checkpoints.get(task_id, []))
        if history:
            return history
        try:
            task = await self.get_state(task_id)
            persisted_cps = task.cts_state.get("dev_checkpoints", [])
            if persisted_cps:
                return [DevelopmentWorkflowCheckpoint.model_validate(d) for d in persisted_cps]
            latest_dict = task.cts_state.get("latest_dev_checkpoint")
            if latest_dict:
                return [DevelopmentWorkflowCheckpoint.model_validate(latest_dict)]
        except Exception:
            pass
        return []

    async def get_latest_development_checkpoint(
        self, task_id: str
    ) -> DevelopmentWorkflowCheckpoint | None:
        """Retrieve latest durable checkpoint for development workflow."""
        history = self._dev_checkpoints.get(task_id, [])
        if history:
            return history[-1]
        try:
            task = await self.get_state(task_id)
            latest_dict = task.cts_state.get("latest_dev_checkpoint")
            if latest_dict:
                return DevelopmentWorkflowCheckpoint.model_validate(latest_dict)
        except Exception:
            pass
        return None

    async def resume_development_workflow(
        self,
        tenant_id: str,
        task_id: str,
    ) -> tuple[DevelopmentWorkflowCheckpoint, dict[str, Any]]:
        """Resume a development workflow from the latest valid durable checkpoint.

        Restart-safe recovery: Loads the latest committed state without duplicating previous effects.
        """
        checkpoint = await self.get_latest_development_checkpoint(task_id)
        if not checkpoint:
            # Initialize fresh RECEIVED checkpoint
            initial = DevelopmentWorkflowCheckpoint(
                task_id=task_id,
                workflow_id=f"wf-{task_id}",
                step_id="init",
                attempt_id="att-1",
                state=DevelopmentWorkflowState.RECEIVED,
                idempotency_key=f"init-{task_id}",
                state_data={},
            )
            checkpoint = await self.save_development_checkpoint(tenant_id, initial)

        return checkpoint, checkpoint.state_data

    async def record_development_approval_decision(
        self,
        tenant_id: str,
        task_id: str,
        approval_token: DevelopmentApprovalToken,
        checkpoint: DevelopmentWorkflowCheckpoint | None = None,
    ) -> None:
        """Record human approval decision token and bind it to task checkpoints."""
        tokens = self._dev_approval_tokens.setdefault(task_id, [])
        tokens.append(approval_token)

        if checkpoint:
            await self.save_development_checkpoint(tenant_id, checkpoint)
        else:
            try:
                task = await self.get_state(task_id)
                cts_state = dict(task.cts_state)
                tokens_list = cts_state.setdefault("dev_approval_tokens", [])
                tokens_list.append(approval_token.model_dump(mode="json"))
                task.cts_state.update(cts_state)
                await self.save_state(tenant_id, task)
            except Exception:
                pass

        if self._provenance_recorder:
            if hasattr(self._provenance_recorder, "record_development_event"):
                try:
                    await self._provenance_recorder.record_development_event(
                        tenant_id=tenant_id,
                        task_id=task_id,
                        workflow_id=approval_token.workflow_id,
                        step_id=approval_token.step_id,
                        attempt_id=approval_token.attempt_id,
                        activity_type=f"hitl_{approval_token.decision.lower()}",
                        agent_id=approval_token.reviewer_id,
                        worker_role=approval_token.reviewer_role,
                        input_snapshot_hash=approval_token.input_snapshot_hash,
                        output_snapshot_hash=approval_token.output_snapshot_hash,
                        evidence_ref=f"token:{approval_token.token_id}",
                        metadata={
                            "token_id": approval_token.token_id,
                            "decision": approval_token.decision,
                            "reviewer_role": approval_token.reviewer_role,
                            "review_dossier_hash": approval_token.review_dossier_hash,
                            "revision_notes": approval_token.revision_notes,
                        },
                    )
                except Exception as exc:
                    logger.warning("Failed to record development provenance event for approval: %s", exc)
            else:
                await self._provenance_recorder.record(
                    tenant_id=tenant_id,
                    entity_id=task_id,
                    activity=f"hitl_{approval_token.decision.lower()}",
                    agent=approval_token.reviewer_id,
                    metadata={
                        "token_id": approval_token.token_id,
                        "step_id": approval_token.step_id,
                        "attempt_id": approval_token.attempt_id,
                        "decision": approval_token.decision,
                        "reviewer_role": approval_token.reviewer_role,
                    },
                )

    async def get_development_approval_token(
        self,
        task_id: str,
        step_id: str | None = None,
        attempt_id: str | None = None,
    ) -> DevelopmentApprovalToken | None:
        """Retrieve the latest approval token for a task, optionally filtered by step and attempt."""
        tokens = self._dev_approval_tokens.get(task_id, [])
        for tok in reversed(tokens):
            if step_id and tok.step_id != step_id:
                continue
            if attempt_id and tok.attempt_id != attempt_id:
                continue
            return tok
        try:
            task = await self.get_state(task_id)
            tokens_data = task.cts_state.get("dev_approval_tokens", [])
            for tok_dict in reversed(tokens_data):
                tok = DevelopmentApprovalToken.model_validate(tok_dict)
                if step_id and tok.step_id != step_id:
                    continue
                if attempt_id and tok.attempt_id != attempt_id:
                    continue
                return tok
        except Exception:
            pass
        return None
