# File: context_state_artifacts.py
"""
Context Memory, Canonical Task State, and Immutable Artifact Management.

Architecture:
1. Invocation Context: Ephemeral, token-budgeted working memory for single inference/tool turns.
2. Session Memory: Task-scoped, isolated scratchpads per execution workstream.
3. Long-Term Institutional Memory: Governed, multi-tenant persistent knowledge base with explicit promotion gates.
4. Canonical Task State: Central orchestrator-owned deterministic state machine with checkpointer,
   resumability, rollback, and BLOCKED_HITL pause/resume semantics.
5. Artifact Registry: Immutable, versioned deliverable management with content-addressable storage references.
6. Provenance & Audit: W3C PROV lineage models and a cryptographically chained, tamper-resistant audit ledger.
"""

from __future__ import annotations

import copy
import dataclasses
import enum
import hashlib
import json
import logging
import math
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("context_state_artifacts")


# ============================================================================
# 1. ENUMS AND DATA SCHEMAS
# ============================================================================

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


class MemoryNamespace(str, enum.Enum):
    """Namespaces for durable institutional knowledge."""
    BRAND_RULES = "brand_rules"
    ATTRIBUTION_HEURISTICS = "attribution_heuristics"
    REGULATORY_POLICIES = "regulatory_policies"
    NEGATIVE_CONSTRAINTS = "negative_constraints"
    PRODUCT_SPECS = "product_specs"


class ProvRelationType(str, enum.Enum):
    """W3C PROV core relationship types."""
    USED = "used"
    WAS_GENERATED_BY = "wasGeneratedBy"
    WAS_DERIVED_FROM = "wasDerivedFrom"
    WAS_ATTRIBUTED_TO = "wasAttributedTo"
    WAS_ASSOCIATED_WITH = "wasAssociatedWith"


# ============================================================================
# 2. INVOCATION CONTEXT LAYER (EPHEMERAL & BOUNDED)
# ============================================================================

@dataclasses.dataclass
class StagedReference:
    """Lightweight reference pointing to external evidence or artifacts."""
    reference_id: str
    uri: str
    content_hash: str
    summary_excerpt: str
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


class InvocationContext:
    """
    Ephemeral, bounded, token-budgeted working memory for a single inference/tool call.
    Staged references are used instead of embedding heavy payloads into model context.
    Disposed immediately after turn completion.
    """

    def __init__(self, invocation_id: str, task_id: str, agent_id: str, token_budget: int = 4096):
        self.invocation_id = invocation_id
        self.task_id = task_id
        self.agent_id = agent_id
        self.token_budget = token_budget
        self.tokens_used = 0
        self.staged_references: Dict[str, StagedReference] = {}
        self.prompt_fragments: List[str] = []
        self.is_active = True
        self.created_at = datetime.now(timezone.utc)

    def stage_reference(self, uri: str, content_hash: str, summary: str,
                        metadata: Optional[Dict[str, Any]] = None) -> StagedReference:
        if not self.is_active:
            raise RuntimeError("Cannot stage references on a disposed InvocationContext.")
        ref_id = f"ref_{uuid.uuid4().hex[:8]}"
        ref = StagedReference(
            reference_id=ref_id,
            uri=uri,
            content_hash=content_hash,
            summary_excerpt=summary[:200],
            metadata=metadata or {}
        )
        self.staged_references[ref_id] = ref
        return ref

    def consume_tokens(self, count: int) -> None:
        if not self.is_active:
            raise RuntimeError("Cannot consume tokens on a disposed InvocationContext.")
        self.tokens_used += count
        if self.tokens_used > self.token_budget:
            logger.warning("Token budget exceeded in InvocationContext %s: %d > %d",
                           self.invocation_id, self.tokens_used, self.token_budget)

    def is_budget_exceeded(self) -> bool:
        return self.tokens_used > self.token_budget

    def render_prompt_context(self) -> str:
        """Renders lightweight, stable references without embedding raw artifact bodies."""
        if not self.is_active:
            raise RuntimeError("Cannot render prompt context on a disposed InvocationContext.")
        lines = ["[STAGED EVIDENCE & ARTIFACT REFERENCES]"]
        for ref in self.staged_references.values():
            lines.append(f"- Ref: {ref.reference_id} | URI: {ref.uri} | Hash: {ref.content_hash[:12]}... | Summary: {ref.summary_excerpt}")
        return chr(10).join(lines)

    def dispose(self) -> None:
        """Clears working context to prevent state retention or cross-turn leaks."""
        self.is_active = False
        self.staged_references.clear()
        self.prompt_fragments.clear()
        logger.debug("InvocationContext %s disposed cleanly.", self.invocation_id)


# ============================================================================
# 3. SESSION / SHORT-TERM MEMORY LAYER (TASK/WORKER ISOLATED)
# ============================================================================

@dataclasses.dataclass(frozen=True)
class SessionEntry:
    entry_id: str
    timestamp: datetime
    agent_id: str
    entry_type: str
    content: str
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


class SessionMemory:
    """
    Task-scoped scratchpad for an active execution lifecycle or DAG run.
    Strictly isolated per task and worker; prevents sibling contamination.
    """

    def __init__(self, session_id: str, task_id: str, worker_id: str, tenant_id: str):
        self.session_id = session_id
        self.task_id = task_id
        self.worker_id = worker_id
        self.tenant_id = tenant_id
        self._scratchpad: List[SessionEntry] = []
        self._created_at = datetime.now(timezone.utc)

    def _assert_access(self, requesting_tenant_id: str, requesting_worker_id: str) -> None:
        if requesting_tenant_id != self.tenant_id:
            raise PermissionError(f"Tenant isolation breach: {requesting_tenant_id} != {self.tenant_id}")
        if requesting_worker_id != self.worker_id:
            raise PermissionError(f"Cross-worker session access denied: {requesting_worker_id} cannot access worker {self.worker_id}")

    def record_entry(self, requesting_tenant_id: str, requesting_worker_id: str,
                     entry_type: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> SessionEntry:
        self._assert_access(requesting_tenant_id, requesting_worker_id)
        entry = SessionEntry(
            entry_id=f"ses_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc),
            agent_id=requesting_worker_id,
            entry_type=entry_type,
            content=content,
            metadata=metadata or {}
        )
        self._scratchpad.append(entry)
        return entry

    def get_entries(self, requesting_tenant_id: str, requesting_worker_id: str) -> List[SessionEntry]:
        self._assert_access(requesting_tenant_id, requesting_worker_id)
        return list(self._scratchpad)

    def clear(self, requesting_tenant_id: str, requesting_worker_id: str) -> None:
        self._assert_access(requesting_tenant_id, requesting_worker_id)
        self._scratchpad.clear()


# ============================================================================
# 4. LONG-TERM INSTITUTIONAL MEMORY (GOVERNED & PERSISTENT)
# ============================================================================

@dataclasses.dataclass
class MemoryItem:
    item_id: str
    tenant_id: str
    brand_id: str
    namespace: MemoryNamespace
    title: str
    content: str
    version: int
    effective_timestamp: datetime
    promoted_by: str
    promotion_justification: str
    provenance_ref: str
    is_active: bool = True
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class PromotionProposal:
    proposal_id: str
    tenant_id: str
    brand_id: str
    namespace: MemoryNamespace
    title: str
    content: str
    justification: str
    proposing_agent_id: str
    created_at: datetime
    is_reviewed: bool = False
    is_approved: bool = False
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None


class InstitutionalMemoryStore:
    """
    Durable, central-authority-owned institutional memory.
    Requires explicit, governed promotion workflow before persistence.
    """

    def __init__(self):
        self._items: Dict[str, MemoryItem] = {}
        self._proposals: Dict[str, PromotionProposal] = {}

    def propose_promotion(self, tenant_id: str, brand_id: str, namespace: MemoryNamespace,
                          title: str, content: str, justification: str,
                          proposing_agent_id: str) -> PromotionProposal:
        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
        proposal = PromotionProposal(
            proposal_id=proposal_id,
            tenant_id=tenant_id,
            brand_id=brand_id,
            namespace=namespace,
            title=title,
            content=content,
            justification=justification,
            proposing_agent_id=proposing_agent_id,
            created_at=datetime.now(timezone.utc)
        )
        self._proposals[proposal_id] = proposal
        logger.info("Promotion proposal %s registered by agent %s for namespace %s",
                    proposal_id, proposing_agent_id, namespace.value)
        return proposal

    def review_promotion(self, proposal_id: str, reviewer_id: str,
                         approved: bool, review_notes: str,
                         provenance_ref: str = "") -> Optional[MemoryItem]:
        if proposal_id not in self._proposals:
            raise KeyError(f"Proposal {proposal_id} not found.")
        proposal = self._proposals[proposal_id]
        if proposal.is_reviewed:
            raise ValueError(f"Proposal {proposal_id} has already been reviewed.")

        proposal.is_reviewed = True
        proposal.is_approved = approved
        proposal.reviewed_by = reviewer_id
        proposal.review_notes = review_notes

        if not approved:
            logger.info("Promotion proposal %s rejected by %s: %s", proposal_id, reviewer_id, review_notes)
            return None

        # Create promoted durable item
        item_id = f"mem_{uuid.uuid4().hex[:12]}"
        item = MemoryItem(
            item_id=item_id,
            tenant_id=proposal.tenant_id,
            brand_id=proposal.brand_id,
            namespace=proposal.namespace,
            title=proposal.title,
            content=proposal.content,
            version=1,
            effective_timestamp=datetime.now(timezone.utc),
            promoted_by=reviewer_id,
            promotion_justification=proposal.justification,
            provenance_ref=provenance_ref or f"proposal:{proposal_id}",
            is_active=True
        )
        self._items[item_id] = item
        logger.info("Promotion proposal %s APPROVED. Persisted institutional memory item %s.",
                    proposal_id, item_id)
        return item

    def query(self, tenant_id: str, namespace: MemoryNamespace,
              filter_query: Optional[str] = None) -> List[MemoryItem]:
        results: List[MemoryItem] = []
        for item in self._items.values():
            if item.tenant_id != tenant_id or not item.is_active:
                continue
            if item.namespace != namespace:
                continue
            if filter_query:
                tokens = set(re.findall(r"\w+", filter_query.lower()))
                item_tokens = set(re.findall(r"\w+", (item.title + " " + item.content).lower()))
                if not tokens.intersection(item_tokens):
                    continue
            results.append(item)
        return results


# ============================================================================
# 5. IMMUTABLE ARTIFACT REGISTRY
# ============================================================================

@dataclasses.dataclass(frozen=True)
class ArtifactReference:
    """Stable reference passed into model contexts in lieu of raw artifact bodies."""
    artifact_id: str
    tenant_id: str
    name: str
    version: int
    content_hash: str
    storage_uri: str
    mime_type: str


@dataclasses.dataclass(frozen=True)
class Artifact:
    """Immutable deliverable stored persistently outside context."""
    artifact_id: str
    tenant_id: str
    brand_id: str
    name: str
    version: int
    parent_artifact_id: Optional[str]
    content_hash: str
    storage_uri: str
    content_payload: str
    mime_type: str
    created_by_agent: str
    created_at: datetime
    is_approved: bool
    evidence_refs: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_reference(self) -> ArtifactReference:
        return ArtifactReference(
            artifact_id=self.artifact_id,
            tenant_id=self.tenant_id,
            name=self.name,
            version=self.version,
            content_hash=self.content_hash,
            storage_uri=self.storage_uri,
            mime_type=self.mime_type
        )


class ArtifactRegistry:
    """
    Persistent store for deliverables and inspectable outputs.
    Artifacts are strictly immutable: updates produce new derivative versions.
    """

    def __init__(self, base_storage_uri: str = "s3://enterprise-artifact-registry"):
        self.base_storage_uri = base_storage_uri.rstrip("/")
        self._artifacts: Dict[str, Artifact] = {}
        self._artifact_lineage: Dict[str, List[str]] = {}

    @staticmethod
    def compute_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def register_artifact(self, tenant_id: str, brand_id: str, name: str,
                          content_payload: str, mime_type: str,
                          created_by_agent: str, evidence_refs: Optional[Sequence[str]] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Artifact:
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        content_hash = self.compute_hash(content_payload)
        storage_uri = f"{self.base_storage_uri}/{tenant_id}/{name}/v1/{content_hash[:12]}"

        artifact = Artifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            brand_id=brand_id,
            name=name,
            version=1,
            parent_artifact_id=None,
            content_hash=content_hash,
            storage_uri=storage_uri,
            content_payload=content_payload,
            mime_type=mime_type,
            created_by_agent=created_by_agent,
            created_at=datetime.now(timezone.utc),
            is_approved=False,
            evidence_refs=tuple(evidence_refs or ()),
            metadata=metadata or {}
        )
        self._artifacts[artifact_id] = artifact
        self._artifact_lineage[name] = [artifact_id]
        logger.info("Registered initial artifact %s ('%s' v1) with hash %s",
                    artifact_id, name, content_hash[:8])
        return artifact

    def create_derivative(self, parent_artifact_id: str, content_payload: str,
                          created_by_agent: str, evidence_refs: Optional[Sequence[str]] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Artifact:
        """Enforces immutability by creating a new derivative version linked to parent."""
        if parent_artifact_id not in self._artifacts:
            raise KeyError(f"Parent artifact {parent_artifact_id} does not exist.")

        parent = self._artifacts[parent_artifact_id]
        new_version = parent.version + 1
        new_id = f"art_{uuid.uuid4().hex[:12]}"
        new_hash = self.compute_hash(content_payload)
        new_storage_uri = f"{self.base_storage_uri}/{parent.tenant_id}/{parent.name}/v{new_version}/{new_hash[:12]}"

        derivative = Artifact(
            artifact_id=new_id,
            tenant_id=parent.tenant_id,
            brand_id=parent.brand_id,
            name=parent.name,
            version=new_version,
            parent_artifact_id=parent_artifact_id,
            content_hash=new_hash,
            storage_uri=new_storage_uri,
            content_payload=content_payload,
            mime_type=parent.mime_type,
            created_by_agent=created_by_agent,
            created_at=datetime.now(timezone.utc),
            is_approved=False,
            evidence_refs=tuple(evidence_refs or parent.evidence_refs),
            metadata=metadata or parent.metadata
        )
        self._artifacts[new_id] = derivative
        self._artifact_lineage[parent.name].append(new_id)
        logger.info("Created derivative artifact %s ('%s' v%d) derived from %s",
                    new_id, parent.name, new_version, parent_artifact_id)
        return derivative

    def get_artifact(self, artifact_id: str) -> Artifact:
        if artifact_id not in self._artifacts:
            raise KeyError(f"Artifact {artifact_id} not found.")
        return self._artifacts[artifact_id]

    def resolve_reference(self, reference: ArtifactReference) -> Artifact:
        art = self.get_artifact(reference.artifact_id)
        if art.content_hash != reference.content_hash:
            raise ValueError(f"Artifact integrity compromised: hash mismatch for {reference.artifact_id}")
        return art


# ============================================================================
# 6. W3C PROV PROVENANCE & IMMUTABLE AUDIT LEDGER
# ============================================================================

@dataclasses.dataclass
class ProvEntity:
    entity_id: str
    entity_type: str
    attributes: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class ProvActivity:
    activity_id: str
    activity_type: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    attributes: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class ProvAgent:
    agent_id: str
    agent_type: str
    attributes: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class ProvStatement:
    statement_id: str
    relation_type: ProvRelationType
    subject_id: str
    object_id: str
    timestamp: datetime
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class AuditRecord:
    record_id: str
    sequence_number: int
    timestamp_iso: str
    actor_id: str
    action_type: str
    payload_hash: str
    details: Dict[str, Any]
    previous_hash: str
    record_hash: str


class ImmutableAuditLedger:
    """
    Append-only, cryptographically chained audit ledger.
    Ensures complete forensic traceability across state mutations and approvals.
    """

    GENESIS_HASH = "0" * 64

    def __init__(self):
        self._chain: List[AuditRecord] = []
        self._prov_entities: Dict[str, ProvEntity] = {}
        self._prov_activities: Dict[str, ProvActivity] = {}
        self._prov_agents: Dict[str, ProvAgent] = {}
        self._prov_statements: List[ProvStatement] = []

    def record_prov_statement(self, relation: ProvRelationType, subject_id: str,
                              object_id: str, metadata: Optional[Dict[str, Any]] = None) -> ProvStatement:
        statement = ProvStatement(
            statement_id=f"prov_{uuid.uuid4().hex[:8]}",
            relation_type=relation,
            subject_id=subject_id,
            object_id=object_id,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        self._prov_statements.append(statement)
        return statement

    def append_entry(self, actor_id: str, action_type: str, details: Dict[str, Any]) -> AuditRecord:
        seq = len(self._chain)
        prev_hash = self._chain[-1].record_hash if self._chain else self.GENESIS_HASH
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        
        payload_serialized = json.dumps(details, sort_keys=True)
        payload_hash = hashlib.sha256(payload_serialized.encode("utf-8")).hexdigest()

        block_content = f"{seq}::{timestamp_iso}::{actor_id}::{action_type}::{payload_hash}::{prev_hash}"
        record_hash = hashlib.sha256(block_content.encode("utf-8")).hexdigest()

        record = AuditRecord(
            record_id=f"rec_{uuid.uuid4().hex[:8]}",
            sequence_number=seq,
            timestamp_iso=timestamp_iso,
            actor_id=actor_id,
            action_type=action_type,
            payload_hash=payload_hash,
            details=copy.deepcopy(details),
            previous_hash=prev_hash,
            record_hash=record_hash
        )
        self._chain.append(record)
        return record

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """Verifies cryptographic linkage from genesis to head."""
        for idx, record in enumerate(self._chain):
            expected_prev = self._chain[idx - 1].record_hash if idx > 0 else self.GENESIS_HASH
            if record.previous_hash != expected_prev:
                return False, f"Broken chain link at seq {record.sequence_number}: expected {expected_prev}, got {record.previous_hash}"

            payload_serialized = json.dumps(record.details, sort_keys=True)
            recomputed_payload_hash = hashlib.sha256(payload_serialized.encode("utf-8")).hexdigest()
            if record.payload_hash != recomputed_payload_hash:
                return False, f"Tampered payload at seq {record.sequence_number}"

            block_content = f"{record.sequence_number}::{record.timestamp_iso}::{record.actor_id}::{record.action_type}::{record.payload_hash}::{record.previous_hash}"
            recomputed_block_hash = hashlib.sha256(block_content.encode("utf-8")).hexdigest()
            if record.record_hash != recomputed_block_hash:
                return False, f"Invalid block hash at seq {record.sequence_number}"

        return True, None

    def get_chain(self) -> List[AuditRecord]:
        return list(self._chain)


# ============================================================================
# 7. CANONICAL TASK STATE MACHINE & CHECKPOINTER
# ============================================================================

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
    State machine and checkpointer owned exclusively by the central orchestrator.
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
            raise KeyError(f"Checkpoint {checkpoint_id} not found.")

        cp = self._checkpoints[checkpoint_id]
        expected_hash = self._compute_state_hash(cp.state_payload, cp.status)
        if cp.state_hash != expected_hash:
            raise ValueError(f"Checkpoint {checkpoint_id} state hash corrupted; aborting rollback.")

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