"""W3C PROV-compliant audit-event contracts for sandbox execution and governance.

Each record references the hash of the record immediately before it,
forming an append-only, tamper-evident hash chain per tenant.
Provides full mapping for W3C PROV Entities, Activities, Agents, and
their ontological relationships.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ProvRelationType(StrEnum):
    """Standard W3C PROV relation terms."""

    WAS_ASSOCIATED_WITH = "prov:wasAssociatedWith"
    USED = "prov:used"
    WAS_GENERATED_BY = "prov:wasGeneratedBy"
    WAS_DERIVED_FROM = "prov:wasDerivedFrom"
    WAS_ATTRIBUTED_TO = "prov:wasAttributedTo"
    ACTED_ON_BEHALF_OF = "prov:actedOnBehalfOf"


class W3CProvActivity(BaseModel):
    """W3C PROV Activity: an action that occurs over a period of time."""

    id: str
    type: str = "prov:Activity"
    label: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class W3CProvAgent(BaseModel):
    """W3C PROV Agent: an entity that bears responsibility for an activity."""

    id: str
    type: str = "prov:Agent"
    label: str
    role: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class W3CProvEntity(BaseModel):
    """W3C PROV Entity: a physical, digital, or conceptual item."""

    id: str
    type: str = "prov:Entity"
    label: str
    value_hash: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class W3CProvRelation(BaseModel):
    """W3C PROV Directed Relation connecting entities, activities, and agents."""

    relation_type: ProvRelationType
    source_id: str
    target_id: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class W3CProvBundle(BaseModel):
    """Complete W3C PROV bundle describing an execution graph."""

    activities: list[W3CProvActivity] = Field(default_factory=list)
    agents: list[W3CProvAgent] = Field(default_factory=list)
    entities: list[W3CProvEntity] = Field(default_factory=list)
    relations: list[W3CProvRelation] = Field(default_factory=list)


class SandboxExecutionAuditMetadata(BaseModel):
    """Structured audit metadata for sandbox invocation and resource metrics."""

    execution_id: str
    task_id: str
    worker_role: str
    capability: str
    operation: str
    lifecycle_stage: str  # "requested" | "started" | "completed" | "failed" | "timed_out" | "killed"
    status: str
    exit_code: int | None = None
    duration_ms: float = 0.0
    command: str | None = None
    egress_grant_id: str | None = None
    resources: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    error_details: str | None = None


class ProvenanceRecord(BaseModel):
    """A single immutable entity/activity/agent audit-lineage entry with W3C PROV payload."""

    record_id: str
    tenant_id: str
    entity_id: str
    activity: str
    agent: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    prev_record_hash: str | None = None
    metadata_hash: str | None = None
    record_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    w3c_prov: dict[str, Any] = Field(default_factory=dict)


class AuditLineageStage(StrEnum):
    """Pipeline stages verified during end-to-end audit lineage validation."""

    GOVERNANCE = "governance"
    ORCHESTRATION = "orchestration"
    RAG = "rag"
    WORKER_SANDBOX = "worker_sandbox"
    HITL_APPROVAL = "hitl_approval"
    MCP_ACTUATION = "mcp_actuation"
    TELEMETRY_T30 = "telemetry_t30"
    LEARNING_T31 = "learning_t31"


class AuditValidationFinding(BaseModel):
    """Specific finding or gap identified during audit lineage validation."""

    stage: str
    entity_id: str | None = None
    activity: str | None = None
    agent: str | None = None
    status: str = "VALID"  # "VALID" | "GAP" | "TAMPERED" | "MISMATCH" | "INVALID_SIGNATURE"
    details: str = ""


class AuditValidationReport(BaseModel):
    """Consolidated outcome of end-to-end audit lineage and ledger integrity verification."""

    validation_id: str
    tenant_id: str
    is_valid: bool
    t30_status: str
    t31_status: str
    chain_length: int
    hash_chain_verified: bool
    signatures_verified: bool
    cts_reconciled: bool
    prov_graph_valid: bool
    stages_verified: list[str] = Field(default_factory=list)
    detected_gaps: list[str] = Field(default_factory=list)
    findings: list[AuditValidationFinding] = Field(default_factory=list)
    t34_audit_eligible: bool = False
    validated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))