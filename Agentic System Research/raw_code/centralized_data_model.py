# File: centralized_data_model.py
"""
Centralized Enterprise Data Model & Governed Persistence Layer.

Singular System of Record:
- Central Enterprise Database & Headless CMS form the authoritative persistence plane.
- Every durable entity strictly requires the 7-tuple governance metadata:
  <tenant_or_brand_id, owner, schema_version, freshness_timestamp, access_policy, lineage, retention_metadata>
- Anti-Replication: Prohibits persistent agent-local shadow copies; enforces transient working memory.
- Governed Ingress: Subordinate agents submit write proposals; only orchestrator commits to persistence.
- Governed Egress: Reads occur only through policy-enforcing gateways with tenant and sensitivity filtering.
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
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger("centralized_data_model")


# ============================================================================
# 1. CORE ENUMS & POLICY VALUES
# ============================================================================

class SensitivityLevel(enum.IntEnum):
    """Hierarchical sensitivity classification for access control."""
    PUBLIC = 1
    INTERNAL = 2
    CONFIDENTIAL = 3
    RESTRICTED = 4


class FreshnessStatus(str, enum.Enum):
    """Temporal validity state of a record."""
    CURRENT = "current"
    STALE = "stale"
    EXPIRED = "expired"
    UNVERIFIED = "unverified"


class RetentionClass(str, enum.Enum):
    """Data retention lifecycle categories."""
    EPHEMERAL_30D = "ephemeral_30d"
    OPERATIONAL_1YR = "operational_1yr"
    REGULATORY_7YR = "regulatory_7yr"
    PERMANENT_RECORD = "permanent_record"
    LEGAL_HOLD = "legal_hold"


class ProposalStatus(str, enum.Enum):
    """Lifecycle of an agent-submitted write proposal."""
    PENDING_VALIDATION = "pending_validation"
    VALIDATED = "validated"
    COMMITTED = "committed"
    REJECTED = "rejected"


class DirectWriteBlockedError(PermissionError):
    """Raised when an agent attempts to bypass orchestrator-controlled persistence."""
    pass


class TenantIsolationError(PermissionError):
    """Raised when a cross-tenant read or write boundary is violated."""
    pass


class PolicyAccessDeniedError(PermissionError):
    """Raised when a caller lacks sensitivity or role clearance."""
    pass


class SchemaContractError(ValueError):
    """Raised when a payload violates its declared schema version or structure."""
    pass


# ============================================================================
# 2. MANDATORY SEVEN-TUPLE GOVERNANCE METADATA CONTRACT
# ============================================================================

@dataclasses.dataclass(frozen=True)
class FreshnessMetadata:
    """Temporal validity dimensions of the record."""
    effective_timestamp: datetime
    observed_timestamp: datetime
    indexed_timestamp: datetime

    def evaluate_status(self, max_age_seconds: Optional[float] = None,
                        freshness_target: Optional[datetime] = None) -> FreshnessStatus:
        now = datetime.now(timezone.utc)
        eff = self.effective_timestamp if self.effective_timestamp.tzinfo else self.effective_timestamp.replace(tzinfo=timezone.utc)
        
        if freshness_target:
            target = freshness_target if freshness_target.tzinfo else freshness_target.replace(tzinfo=timezone.utc)
            if eff < target:
                return FreshnessStatus.STALE

        if max_age_seconds is not None:
            age = (now - eff).total_seconds()
            if age > max_age_seconds:
                return FreshnessStatus.STALE

        return FreshnessStatus.CURRENT


@dataclasses.dataclass(frozen=True)
class AccessPolicy:
    """Authorization and sensitivity constraints evaluated before context staging."""
    sensitivity: SensitivityLevel
    allowed_roles: Tuple[str, ...] = ("*",)
    disallowed_roles: Tuple[str, ...] = ()
    export_restricted: bool = False
    requires_explicit_consent: bool = False

    def is_authorized(self, caller_roles: Set[str], caller_sensitivity_ceiling: SensitivityLevel) -> bool:
        if self.sensitivity > caller_sensitivity_ceiling:
            return False
        if any(role in self.disallowed_roles for role in caller_roles):
            return False
        if "*" in self.allowed_roles:
            return True
        return bool(caller_roles.intersection(set(self.allowed_roles)))


@dataclasses.dataclass(frozen=True)
class LineageRecord:
    """Cryptographic provenance conforming to W3C PROV principles."""
    root_source_uri: str
    parent_entity_ids: Tuple[str, ...]
    activity_type: str
    provenance_hash: str
    created_by_agent: str
    w3c_prov_attributes: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @staticmethod
    def generate_hash(content: str, source_uri: str, version: str) -> str:
        raw = f"{source_uri}::{version}::{content.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class RetentionMetadata:
    """Lifecycle, archival, legal-hold, and regulatory purge parameters."""
    retention_class: RetentionClass
    created_at: datetime
    expires_at: Optional[datetime] = None
    legal_hold: bool = False
    purge_after_expiry: bool = True

    def is_purgeable(self) -> bool:
        if self.legal_hold:
            return False
        if self.retention_class == RetentionClass.PERMANENT_RECORD:
            return False
        if self.expires_at is None:
            return False
        now = datetime.now(timezone.utc)
        exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return now >= exp and self.purge_after_expiry


@dataclasses.dataclass(frozen=True)
class GovernanceMetadata:
    """
    Mandatory 7-tuple contract:
    <tenant_or_brand_id, owner, schema_version, freshness_timestamp, access_policy, lineage, retention_metadata>
    Must accompany every durable enterprise entity without exception.
    """
    tenant_or_brand_id: str
    owner: str
    schema_version: str
    freshness: FreshnessMetadata
    access_policy: AccessPolicy
    lineage: LineageRecord
    retention: RetentionMetadata

    def validate(self) -> None:
        if not self.tenant_or_brand_id or not self.tenant_or_brand_id.strip():
            raise ValueError("GovernanceMetadata violation: tenant_or_brand_id must be non-empty.")
        if not self.owner or not self.owner.strip():
            raise ValueError("GovernanceMetadata violation: owner must be explicitly identified.")
        if not self.schema_version or not self.schema_version.strip():
            raise ValueError("GovernanceMetadata violation: schema_version must be explicitly stated.")
        if not self.freshness:
            raise ValueError("GovernanceMetadata violation: freshness metadata missing.")
        if not self.access_policy:
            raise ValueError("GovernanceMetadata violation: access_policy missing.")
        if not self.lineage or not self.lineage.provenance_hash:
            raise ValueError("GovernanceMetadata violation: lineage or cryptographic hash missing.")
        if not self.retention:
            raise ValueError("GovernanceMetadata violation: retention metadata missing.")


# ============================================================================
# 3. ENTITY MODELS (PERSISTENT REPOSITORIES)
# ============================================================================

@dataclasses.dataclass
class EnterpriseRecord:
    """Canonical business entity (product catalog, customer feedback, strategy brief)."""
    entity_id: str
    entity_type: str
    payload: Dict[str, Any]
    governance: GovernanceMetadata

    def __post_init__(self):
        self.governance.validate()


@dataclasses.dataclass
class ContentModelRecord:
    """Headless CMS content schema, layout, or design token entity."""
    content_id: str
    content_type: str
    schema_name: str
    body: Dict[str, Any]
    governance: GovernanceMetadata
    is_published: bool = False

    def __post_init__(self):
        self.governance.validate()


@dataclasses.dataclass
class VectorChunkRecord:
    """Vector embedding chunk with mandatory tenant and governance bounds."""
    chunk_id: str
    document_uri: str
    text_content: str
    embedding: List[float]
    domain: str
    governance: GovernanceMetadata

    def __post_init__(self):
        self.governance.validate()


@dataclasses.dataclass
class DurableArtifactRecord:
    """Immutable deliverable persisted in the central repository."""
    artifact_id: str
    name: str
    version: int
    parent_artifact_id: Optional[str]
    mime_type: str
    storage_uri: str
    content_payload: str
    governance: GovernanceMetadata

    def __post_init__(self):
        self.governance.validate()


@dataclasses.dataclass
class OperationalRecord:
    """Canonical operational telemetry, state trace, and execution metrics entity."""
    record_id: str
    operation_type: str
    metrics: Dict[str, Any]
    governance: GovernanceMetadata

    def __post_init__(self):
        self.governance.validate()


# ============================================================================
# 4. WRITE PROPOSAL & ORCHESTRATOR COMMIT ENGINE
# ============================================================================

@dataclasses.dataclass(frozen=True)
class WriteProposal:
    """Candidate mutation submitted by a subordinate agent. Never a direct mutation."""
    proposal_id: str
    tenant_id: str
    proposing_agent_id: str
    target_store: str  # "database" | "cms" | "vector" | "artifact" | "operational"
    operation: str     # "INSERT" | "UPDATE_VERSION" | "ARCHIVE"
    entity_id: str
    proposed_payload: Dict[str, Any]
    proposed_governance: GovernanceMetadata
    justification: str
    timestamp: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))


class OrchestratorCommitGate:
    """
    Central Orchestrator persistence gatekeeper.
    Validates proposals against authorization, tenant bounds, schemas, lineage,
    and retention before committing to the Central Enterprise Database.
    """

    def __init__(self, orchestrator_id: str, central_db: CentralEnterpriseDatabase,
                 headless_cms: HeadlessCMSStore):
        self.orchestrator_id = orchestrator_id
        self.central_db = central_db
        self.headless_cms = headless_cms
        self._proposals: Dict[str, WriteProposal] = {}
        self._commit_log: List[Dict[str, Any]] = []

    def submit_proposal(self, proposal: WriteProposal) -> str:
        proposal.proposed_governance.validate()
        if proposal.tenant_id != proposal.proposed_governance.tenant_or_brand_id:
            raise TenantIsolationError(f"Tenant mismatch: proposal '{proposal.tenant_id}' != governance '{proposal.proposed_governance.tenant_or_brand_id}'")

        self._proposals[proposal.proposal_id] = proposal
        logger.info("WriteProposal %s registered from agent %s (Target: %s, Op: %s)",
                    proposal.proposal_id, proposal.proposing_agent_id, proposal.target_store, proposal.operation)
        return proposal.proposal_id

    def commit_proposal(self, proposal_id: str, committing_authority: str,
                        approval_token: Optional[str] = None) -> bool:
        """Validates and atomically commits an agent-submitted write proposal."""
        if committing_authority != self.orchestrator_id and not committing_authority.startswith("human_"):
            raise DirectWriteBlockedError("Only the Central Orchestrator or authorized human can commit proposals.")

        if proposal_id not in self._proposals:
            raise KeyError(f"Proposal '{proposal_id}' not found.")

        proposal = self._proposals[proposal_id]
        gov = proposal.proposed_governance
        gov.validate()

        # High-impact checks: if legal hold or restricted, require approval token
        if gov.access_policy.sensitivity == SensitivityLevel.RESTRICTED or gov.retention.legal_hold:
            if not approval_token or not approval_token.startswith("AUTH_SIG_"):
                raise PolicyAccessDeniedError("Commit blocked: High-impact mutation requires valid cryptographic clearance.")

        # Route commit to designated system of record
        if proposal.target_store == "database":
            record = EnterpriseRecord(
                entity_id=proposal.entity_id,
                entity_type=proposal.proposed_payload.get("entity_type", "generic"),
                payload=proposal.proposed_payload,
                governance=gov
            )
            self.central_db._internal_commit_record(record)
        elif proposal.target_store == "cms":
            cms_record = ContentModelRecord(
                content_id=proposal.entity_id,
                content_type=proposal.proposed_payload.get("content_type", "article"),
                schema_name=proposal.proposed_payload.get("schema_name", "standard_v1"),
                body=proposal.proposed_payload,
                governance=gov,
                is_published=False
            )
            self.headless_cms._internal_commit_content(cms_record)
        elif proposal.target_store == "vector":
            chunk = VectorChunkRecord(
                chunk_id=proposal.entity_id,
                document_uri=proposal.proposed_payload.get("document_uri", "s3://vault/unknown"),
                text_content=proposal.proposed_payload.get("text_content", ""),
                embedding=proposal.proposed_payload.get("embedding", []),
                domain=proposal.proposed_payload.get("domain", "default"),
                governance=gov
            )
            self.central_db._internal_commit_vector_chunk(chunk)
        elif proposal.target_store == "artifact":
            art = DurableArtifactRecord(
                artifact_id=proposal.entity_id,
                name=proposal.proposed_payload.get("name", "artifact"),
                version=int(proposal.proposed_payload.get("version", 1)),
                parent_artifact_id=proposal.proposed_payload.get("parent_artifact_id"),
                mime_type=proposal.proposed_payload.get("mime_type", "text/plain"),
                storage_uri=proposal.proposed_payload.get("storage_uri", "s3://enterprise-vault/artifact"),
                content_payload=proposal.proposed_payload.get("content_payload", ""),
                governance=gov
            )
            self.central_db._internal_commit_artifact(art)
        elif proposal.target_store in ("operational", "telemetry"):
            op_rec = OperationalRecord(
                record_id=proposal.entity_id,
                operation_type=proposal.proposed_payload.get("operation_type", "metric"),
                metrics=proposal.proposed_payload.get("metrics", proposal.proposed_payload),
                governance=gov
            )
            self.central_db._internal_commit_operational_record(op_rec)
        else:
            raise ValueError(f"Unknown target store '{proposal.target_store}'")

        log_entry = {
            "proposal_id": proposal_id,
            "entity_id": proposal.entity_id,
            "target_store": proposal.target_store,
            "committed_by": committing_authority,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self._commit_log.append(log_entry)
        logger.info("Atomically committed entity %s to store %s via Orchestrator.", proposal.entity_id, proposal.target_store)
        return True


# ============================================================================
# 5. SINGULAR SYSTEMS OF RECORD (DATABASE & HEADLESS CMS)
# ============================================================================

class CentralEnterpriseDatabase:
    """
    The singular central enterprise system of record.
    Houses structured business records, vector embeddings, and artifacts.
    Enforces tenant row-level security (RLS), access policy, and retention lifecycle.
    """

    def __init__(self):
        self._records: Dict[str, EnterpriseRecord] = {}
        self._vector_chunks: Dict[str, VectorChunkRecord] = {}
        self._artifacts: Dict[str, DurableArtifactRecord] = {}
        self._operational_records: Dict[str, OperationalRecord] = {}
        self._schema_contracts: Dict[str, Dict[str, Any]] = {}

    def register_schema_contract(self, schema_name: str, version: str, contract_spec: Dict[str, Any]) -> None:
        key = f"{schema_name}::v{version}"
        self._schema_contracts[key] = contract_spec

    # Direct agent write attempts blocked by design
    def insert_record(self, record: EnterpriseRecord, caller_agent_id: str) -> None:
        raise DirectWriteBlockedError(f"Agent '{caller_agent_id}' cannot mutate CentralEnterpriseDatabase directly. Submit a WriteProposal to the Orchestrator.")

    # Internal commit methods called ONLY by the OrchestratorCommitGate
    def _internal_commit_record(self, record: EnterpriseRecord) -> None:
        record.governance.validate()
        self._records[record.entity_id] = record

    def _internal_commit_vector_chunk(self, chunk: VectorChunkRecord) -> None:
        chunk.governance.validate()
        self._vector_chunks[chunk.chunk_id] = chunk

    def _internal_commit_artifact(self, artifact: DurableArtifactRecord) -> None:
        artifact.governance.validate()
        self._artifacts[artifact.artifact_id] = artifact

    def _internal_commit_operational_record(self, record: OperationalRecord) -> None:
        record.governance.validate()
        self._operational_records[record.record_id] = record

    def purge_expired_records(self) -> int:
        """Executes automated data-minimization purges conforming to GDPR/CCPA policies."""
        purged_count = 0
        now = datetime.now(timezone.utc)
        
        # Purge ordinary records
        for eid, r in list(self._records.items()):
            if r.governance.retention.is_purgeable():
                del self._records[eid]
                purged_count += 1
                logger.info("Retention purge: Deleted expired record %s", eid)

        # Purge vector chunks
        for cid, c in list(self._vector_chunks.items()):
            if c.governance.retention.is_purgeable():
                del self._vector_chunks[cid]
                purged_count += 1
                logger.info("Retention purge: Deleted expired vector chunk %s", cid)

        # Purge operational records
        for oid, o in list(self._operational_records.items()):
            if o.governance.retention.is_purgeable():
                del self._operational_records[oid]
                purged_count += 1
                logger.info("Retention purge: Deleted expired operational record %s", oid)

        return purged_count


class HeadlessCMSStore:
    """
    Authoritative store for content models, pages, templates, and design tokens.
    Isolated per tenant and strictly governed.
    """

    def __init__(self):
        self._content: Dict[str, ContentModelRecord] = {}

    def publish_content(self, content_id: str, caller_agent_id: str) -> None:
        raise DirectWriteBlockedError(f"Agent '{caller_agent_id}' cannot publish CMS content directly. Use Orchestrator staged releases.")

    def _internal_commit_content(self, content: ContentModelRecord) -> None:
        content.governance.validate()
        self._content[content.content_id] = content

    def release_staged_content(self, content_id: str, releasing_authority: str, approval_token: str) -> bool:
        if not releasing_authority.startswith("orchestrator_") and not releasing_authority.startswith("human_"):
            raise DirectWriteBlockedError("Unauthorized release authority.")
        if not approval_token or not approval_token.startswith("AUTH_SIG_"):
            raise PolicyAccessDeniedError("CMS release requires valid cryptographic approval.")
        if content_id not in self._content:
            raise KeyError(f"Content '{content_id}' not found.")

        self._content[content_id].is_published = True
        logger.info("CMS content %s marked as PUBLISHED by %s", content_id, releasing_authority)
        return True


# ============================================================================
# 6. GOVERNED READ GATEWAY (POLICY-ENFORCING ACCESS LAYER)
# ============================================================================

@dataclasses.dataclass(frozen=True)
class CallerContext:
    """Security identity of the calling agent or user."""
    tenant_id: str
    brand_id: str
    agent_id: str
    roles: Set[str]
    sensitivity_ceiling: SensitivityLevel = SensitivityLevel.INTERNAL


@dataclasses.dataclass(frozen=True)
class GovernedReadResult:
    """Read result ensuring policy compliance and context hygiene."""
    entity_id: str
    payload: Dict[str, Any]
    freshness: FreshnessStatus
    lineage_uri: str
    provenance_hash: str


class GovernedReadGateway:
    """
    The only sanctioned egress path for durable enterprise knowledge.
    Enforces tenant isolation, sensitivity clearance, and freshness filtering
    before staging any information into an agent's working context.
    """

    def __init__(self, central_db: CentralEnterpriseDatabase, headless_cms: HeadlessCMSStore):
        self.central_db = central_db
        self.headless_cms = headless_cms

    def read_record(self, caller: CallerContext, entity_id: str,
                    max_age_seconds: Optional[float] = None) -> Optional[GovernedReadResult]:
        if entity_id not in self.central_db._records:
            return None

        record = self.central_db._records[entity_id]
        gov = record.governance

        # 1. Mandatory Tenant Boundary Assertion
        if gov.tenant_or_brand_id != caller.tenant_id:
            raise TenantIsolationError(f"Access Denied: Record tenant '{gov.tenant_or_brand_id}' != caller tenant '{caller.tenant_id}'")

        # 2. Access Policy & Sensitivity Evaluation
        if not gov.access_policy.is_authorized(caller.roles, caller.sensitivity_ceiling):
            raise PolicyAccessDeniedError(f"Access Denied: Caller lacks sensitivity or role clearance for record '{entity_id}'.")

        # 3. Freshness Assessment
        freshness_state = gov.freshness.evaluate_status(max_age_seconds=max_age_seconds)

        return GovernedReadResult(
            entity_id=record.entity_id,
            payload=copy.deepcopy(record.payload),
            freshness=freshness_state,
            lineage_uri=gov.lineage.root_source_uri,
            provenance_hash=gov.lineage.provenance_hash
        )

    def vector_search(self, caller: CallerContext, query_embedding: List[float],
                      domain: str, top_k: int = 5, max_age_seconds: Optional[float] = None) -> List[GovernedReadResult]:
        """Namespaced, tenant-isolated vector search."""
        candidates = []
        for chunk in self.central_db._vector_chunks.values():
            gov = chunk.governance
            # Tenant partition
            if gov.tenant_or_brand_id != caller.tenant_id:
                continue
            # Domain partition
            if chunk.domain != domain:
                continue
            # Sensitivity check
            if not gov.access_policy.is_authorized(caller.roles, caller.sensitivity_ceiling):
                continue

            freshness_state = gov.freshness.evaluate_status(max_age_seconds=max_age_seconds)

            # Cosine similarity calculation
            dot_prod = sum(a * b for a, b in zip(query_embedding, chunk.embedding))
            norm_q = math.sqrt(sum(a * a for a in query_embedding)) or 1.0
            norm_c = math.sqrt(sum(b * b for b in chunk.embedding)) or 1.0
            sim = dot_prod / (norm_q * norm_c)

            candidates.append((sim, chunk, freshness_state))

        candidates.sort(key=lambda x: x[0], reverse=True)
        results = []
        for sim, chunk, f_status in candidates[:top_k]:
            results.append(GovernedReadResult(
                entity_id=chunk.chunk_id,
                payload={"text": chunk.text_content, "similarity": round(sim, 4)},
                freshness=f_status,
                lineage_uri=chunk.governance.lineage.root_source_uri,
                provenance_hash=chunk.governance.lineage.provenance_hash
            ))
        return results


# ============================================================================
# 7. CONTEXT HYGIENE: DISPOSABLE AGENT SCRATCHPAD
# ============================================================================

class EphemeralAgentScratchpad:
    """
    Enforces the Anti-Replication invariant:
    Agent working memory is volatile RAM that cannot write persistent state
    and is automatically purged after execution.
    """

    def __init__(self, agent_id: str, task_id: str, tenant_id: str):
        self.agent_id = agent_id
        self.task_id = task_id
        self.tenant_id = tenant_id
        self._working_notes: List[str] = []
        self._staged_references: List[str] = []
        self.is_active = True

    def write_scratch(self, note: str) -> None:
        if not self.is_active:
            raise RuntimeError("Cannot write to an evicted scratchpad.")
        self._working_notes.append(note)

    def stage_reference(self, reference_id: str) -> None:
        if not self.is_active:
            raise RuntimeError("Cannot stage into an evicted scratchpad.")
        self._staged_references.append(reference_id)

    def dispose(self) -> None:
        """Purges local scratchpad to eliminate local shadow copies."""
        self.is_active = False
        self._working_notes.clear()
        self._staged_references.clear()
        logger.debug("Scratchpad for agent %s on task %s cleanly disposed.", self.agent_id, self.task_id)