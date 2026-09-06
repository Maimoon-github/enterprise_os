# File: canonical_task_state.py
"""
Layer 5: Canonical Task State.

Authoritative deterministic state machine for task execution:
- Owned exclusively by the central orchestrator/intelligence engine.
- Workers and sub-agents submit proposed state deltas, never direct mutations.
- Evaluates transition and acceptance criteria before committing deltas.
- Enforces deterministic checkpointing with state hashing.
- Supports pause/resume for BLOCKED_HITL and historical checkpoint rollback.
"""

from __future__ import annotations

import copy
import dataclasses
import enum
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from audit_provenance import ImmutableAuditLedger

logger = logging.getLogger("canonical_task_state")


class TaskLifecycleStatus(str, enum.Enum):
    """Deterministic lifecycle states of the canonical task state machine."""
    INITIALIZED = "INITIALIZED"
    PLANNING = "PLANNING"
    DELEGATED = "DELEGATED"
    EVALUATING = "EVALUATING"
    BLOCKED_HITL = "BLOCKED_HITL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    HALTED = "HALTED"


@dataclasses.dataclass(frozen=True)
class ProposedStateDelta:
    """Proposed state transition from a subordinate agent. Never a direct mutation."""
    delta_id: str
    task_id: str
    proposing_agent_id: str
    target_status: TaskLifecycleStatus
    state_payload: Dict[str, Any]
    artifact_refs: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    justification: str
    timestamp: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))


@dataclasses.dataclass(frozen=True)
class StateCheckpoint:
    """Immutable persistent snapshot of task state at a specific graph node."""
    checkpoint_id: str
    task_id: str
    node_id: str
    sequence_number: int
    status: TaskLifecycleStatus
    state_payload: Dict[str, Any]
    active_locks: Tuple[str, ...]
    timestamp: datetime
    state_hash: str


class CanonicalTaskStateLedger:
    """
    Central Orchestrator-owned state machine and checkpointer.
    Enforces validation of subordinate deltas, clean pause/resume for BLOCKED_HITL,
    deterministic rollback, and cryptographic audit emission.
    """

    def __init__(self, task_id: str, tenant_id: str, orchestrator_id: str,
                 audit_ledger: ImmutableAuditLedger):
        self.task_id = task_id
        self.tenant_id = tenant_id
        self.orchestrator_id = orchestrator_id
        self.audit_ledger = audit_ledger

        self.current_status = TaskLifecycleStatus.INITIALIZED
        self.canonical_payload: Dict[str, Any] = {}
        self.associated_artifacts: Set[str] = set()
        self.associated_evidence: Set[str] = set()
        self.active_locks: Set[str] = set()

        self._checkpoints: Dict[str, StateCheckpoint] = {}
        self._checkpoint_order: List[str] = []
        self._checkpoint_seq = 0

        self.audit_ledger.append_entry(
            actor_id=self.orchestrator_id,
            action_type="TASK_INITIALIZED",
            details={"task_id": self.task_id, "tenant_id": self.tenant_id}
        )

    def _compute_state_hash(self, payload: Dict[str, Any], status: TaskLifecycleStatus) -> str:
        data = f"{self.task_id}::{status.value}::{json.dumps(payload, sort_keys=True)}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def create_checkpoint(self, node_id: str) -> StateCheckpoint:
        """Persists a deterministic checkpoint for rollback and resumability."""
        self._checkpoint_seq += 1
        cp_id = f"cp_{self.task_id}_{self._checkpoint_seq}"
        state_hash = self._compute_state_hash(self.canonical_payload, self.current_status)

        checkpoint = StateCheckpoint(
            checkpoint_id=cp_id,
            task_id=self.task_id,
            node_id=node_id,
            sequence_number=self._checkpoint_seq,
            status=self.current_status,
            state_payload=copy.deepcopy(self.canonical_payload),
            active_locks=tuple(self.active_locks),
            timestamp=datetime.now(timezone.utc),
            state_hash=state_hash
        )
        self._checkpoints[cp_id] = checkpoint
        self._checkpoint_order.append(cp_id)

        self.audit_ledger.append_entry(
            actor_id=self.orchestrator_id,
            action_type="CHECKPOINT_CREATED",
            details={
                "checkpoint_id": cp_id,
                "node_id": node_id,
                "status": self.current_status.value,
                "state_hash": state_hash
            }
        )
        logger.info("Persisted checkpoint %s at node '%s' (status: %s)",
                    cp_id, node_id, self.current_status.value)
        return checkpoint

    def apply_proposed_delta(self, delta: ProposedStateDelta,
                             acceptance_validator: Optional[Callable[[ProposedStateDelta, Dict[str, Any]], Tuple[bool, str]]] = None) -> bool:
        """
        Applies a proposed state delta after validating acceptance criteria.
        Subordinate agents cannot directly mutate canonical state.
        """
        if delta.task_id != self.task_id:
            raise ValueError(f"Task mismatch: delta task {delta.task_id} != canonical task {self.task_id}")

        if delta.proposing_agent_id == self.orchestrator_id:
            raise PermissionError("Orchestrator applies transitions; workers propose deltas.")

        if acceptance_validator:
            passed, reason = acceptance_validator(delta, self.canonical_payload)
            if not passed:
                logger.warning("Proposed delta %s rejected: %s", delta.delta_id, reason)
                self.audit_ledger.append_entry(
                    actor_id=self.orchestrator_id,
                    action_type="DELTA_REJECTED",
                    details={"delta_id": delta.delta_id, "reason": reason, "proposer": delta.proposing_agent_id}
                )
                return False

        old_status = self.current_status
        self.current_status = delta.target_status
        self.canonical_payload.update(delta.state_payload)
        self.associated_artifacts.update(delta.artifact_refs)
        self.associated_evidence.update(delta.evidence_refs)

        self.audit_ledger.append_entry(
            actor_id=self.orchestrator_id,
            action_type="STATE_TRANSITION_COMMITTED",
            details={
                "delta_id": delta.delta_id,
                "proposing_agent": delta.proposing_agent_id,
                "from_status": old_status.value,
                "to_status": self.current_status.value,
                "artifacts_linked": list(delta.artifact_refs),
                "evidence_linked": list(delta.evidence_refs)
            }
        )
        logger.info("Committed state transition: %s -> %s via delta %s",
                    old_status.value, self.current_status.value, delta.delta_id)
        return True

    def pause_for_hitl(self, reason: str, action_preview_payload: Dict[str, Any]) -> StateCheckpoint:
        """
        Enters BLOCKED_HITL state, persists an authoritative checkpoint,
        and halts execution pending explicit human decision.
        """
        self.current_status = TaskLifecycleStatus.BLOCKED_HITL
        self.canonical_payload["hitl_pause_reason"] = reason
        self.canonical_payload["hitl_action_preview"] = action_preview_payload
        self.active_locks.add("LOCK_HITL_SUSPENSION")

        cp = self.create_checkpoint(node_id="hitl_gate")
        self.audit_ledger.append_entry(
            actor_id=self.orchestrator_id,
            action_type="HITL_PAUSE_TRIGGERED",
            details={"reason": reason, "checkpoint_id": cp.checkpoint_id}
        )
        logger.warning("Task %s paused at BLOCKED_HITL. Checkpoint: %s", self.task_id, cp.checkpoint_id)
        return cp

    def resume_from_hitl(self, approval_token: str, reviewer_id: str,
                         signature_validator: Callable[[str], bool]) -> bool:
        """Resumes an execution paused at BLOCKED_HITL using verifiable cryptographic signature."""
        if self.current_status != TaskLifecycleStatus.BLOCKED_HITL:
            raise ValueError(f"Task is not paused in BLOCKED_HITL (current status: {self.current_status.value})")

        if not signature_validator(approval_token):
            logger.error("Invalid signature token during HITL resumption for task %s", self.task_id)
            self.audit_ledger.append_entry(
                actor_id=self.orchestrator_id,
                action_type="HITL_RESUME_FAILED",
                details={"reviewer_id": reviewer_id, "reason": "Invalid signature"}
            )
            return False

        self.current_status = TaskLifecycleStatus.APPROVED
        self.active_locks.discard("LOCK_HITL_SUSPENSION")
        self.canonical_payload["hitl_approval"] = {
            "reviewer_id": reviewer_id,
            "approval_token": approval_token,
            "resumed_at": datetime.now(timezone.utc).isoformat()
        }

        self.create_checkpoint(node_id="hitl_cleared")
        self.audit_ledger.append_entry(
            actor_id=reviewer_id,
            action_type="HITL_APPROVAL_GRANTED",
            details={"reviewer_id": reviewer_id, "task_id": self.task_id}
        )
        logger.info("Task %s successfully resumed from BLOCKED_HITL by %s", self.task_id, reviewer_id)
        return True

    def rollback_to_checkpoint(self, checkpoint_id: str) -> None:
        """Rolls back canonical task state to an immutable historical checkpoint."""
        if checkpoint_id not in self._checkpoints:
            raise KeyError(f"Checkpoint '{checkpoint_id}' not found.")

        cp = self._checkpoints[checkpoint_id]
        expected_hash = self._compute_state_hash(cp.state_payload, cp.status)
        if cp.state_hash != expected_hash:
            raise ValueError(f"Checkpoint '{checkpoint_id}' state hash corrupted; aborting rollback.")

        old_status = self.current_status
        self.current_status = TaskLifecycleStatus.ROLLED_BACK
        self.canonical_payload = copy.deepcopy(cp.state_payload)
        self.active_locks = set(cp.active_locks)

        self.audit_ledger.append_entry(
            actor_id=self.orchestrator_id,
            action_type="ROLLBACK_EXECUTED",
            details={
                "target_checkpoint": checkpoint_id,
                "from_status": old_status.value,
                "restored_status": cp.status.value,
                "node_id": cp.node_id
            }
        )
        logger.warning("Rolled back task %s to checkpoint %s (node: %s)",
                       self.task_id, checkpoint_id, cp.node_id)