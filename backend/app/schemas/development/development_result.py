"""Typed contracts for W_DEV (Development Engine) core, requests, and deliverables."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.agent_contracts import (
    CodeDiffEntry,
    ConfidenceInterval,
    DevelopmentDeliverable,
    EvidenceEnvelope,
    TaskGrant,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability


DISALLOWED_PATH_PATTERNS = (
    "..",
    "/etc/",
    "c:\\",
    "c:/",
    ".env",
    "credentials",
    "secret",
    "password",
    "shadow",
    "id_rsa",
)

DISALLOWED_TOOL_PREFIXES = (
    "app.persistence",
    "app.services.rag",
    "db_",
    "sql_",
    "outbound_mcp",
    "deploy_",
)


class DevelopmentEngineIdentity(BaseModel):
    """Identity, role, and boundary specification for W_DEV."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    engine_id: str = "W_DEV"
    engine_name: str = "Development Engine"
    worker_role: WorkerRole = WorkerRole.DEVELOPMENT
    version: str = "1.0.0"
    capability: SandboxCapability = SandboxCapability.CODE
    is_subordinate: bool = True
    authority_scope: str = "development_domain_only"


class DevelopmentEngineStatus(BaseModel):
    """Runtime operational state of W_DEV."""

    model_config = ConfigDict(extra="forbid")

    engine_id: str = "W_DEV"
    status: Literal["IDLE", "BUSY", "TERMINATED", "ERROR"] = "IDLE"
    active_task_id: str | None = None
    last_active_at: datetime | None = None
    version: str = "1.0.0"
    supported_operations: list[str] = Field(
        default_factory=lambda: ["generate_diff", "ast_validate", "lint", "execute_subworkflow"]
    )


class DevelopmentTaskGrant(TaskGrant):
    """Bounded, policy-screened task grant issued by Intelligence Engine specifically for W_DEV."""

    model_config = ConfigDict(extra="forbid")

    worker_role: WorkerRole = WorkerRole.DEVELOPMENT
    component_name: str = "Component"
    component_type: str = "component"
    target_files: list[str] = Field(default_factory=list)
    allowed_operations: list[str] = Field(
        default_factory=lambda: ["generate_diff", "ast_validate", "lint"]
    )

    @field_validator("worker_role")
    @classmethod
    def validate_worker_role(cls, value: WorkerRole) -> WorkerRole:
        if value != WorkerRole.DEVELOPMENT:
            raise ValueError(
                f"Invalid worker role '{value}' for DevelopmentTaskGrant; expected '{WorkerRole.DEVELOPMENT.value}'."
            )
        return value

    @field_validator("expires_at")
    @classmethod
    def validate_not_expired(cls, value: datetime) -> datetime:
        now = datetime.now(UTC)
        # Handle naive datetime by converting to UTC
        val_utc = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if val_utc <= now:
            raise ValueError(f"Task grant expired at {val_utc.isoformat()} (current time: {now.isoformat()}).")
        return value

    @field_validator("target_files")
    @classmethod
    def validate_target_files_security(cls, files: list[str]) -> list[str]:
        for f in files:
            f_norm = f.lower().replace("\\", "/").strip()
            if f_norm.startswith("/") or any(p in f_norm for p in DISALLOWED_PATH_PATTERNS):
                raise ValueError(
                    f"Security policy violation: Unauthorized path or traversal pattern in target file '{f}'."
                )
        return files

    @field_validator("sandbox_capabilities")
    @classmethod
    def validate_capabilities(cls, caps: list[str]) -> list[str]:
        for c in caps:
            if c != SandboxCapability.CODE.value:
                raise ValueError(
                    f"Unauthorized sandbox capability '{c}' for W_DEV. Only '{SandboxCapability.CODE.value}' is permitted."
                )
        return caps

    @field_validator("tool_permissions")
    @classmethod
    def validate_tool_permissions(cls, tools: list[str]) -> list[str]:
        for tool in tools:
            tool_lower = tool.lower()
            if any(tool_lower.startswith(prefix) for prefix in DISALLOWED_TOOL_PREFIXES):
                raise ValueError(
                    f"Security policy violation: Tool '{tool}' breaches Model-A boundary for W_DEV."
                )
        return tools


class DevelopmentEngineRequest(BaseModel):
    """Structured invocation payload from Intelligence Engine to W_DEV."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    grant: DevelopmentTaskGrant
    context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_context_tenant_consistency(self) -> DevelopmentEngineRequest:
        grant_tenant = self.grant.tenant_scope.tenant_id if self.grant.tenant_scope else "default"
        ctx_tenant = self.context.get("tenant_id")
        if ctx_tenant and ctx_tenant != grant_tenant:
            raise ValueError(
                f"Tenant isolation breach: Context tenant '{ctx_tenant}' does not match grant tenant '{grant_tenant}'."
            )
        return self


class DevelopmentEngineResult(BaseModel):
    """Structured deliverable and evidence package returned by W_DEV to Intelligence Engine."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    engine_id: str = "W_DEV"
    status: Literal["SUCCESS", "FAILED", "REJECTED"] = "SUCCESS"
    deliverable: DevelopmentDeliverable | None = None
    evidence_envelope: EvidenceEnvelope
    validation_findings: list[str] = Field(default_factory=list)
    error_message: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DependencyChangeAction(StrEnum):
    """Actions applicable to software dependencies."""

    ADD = "ADD"
    REMOVE = "REMOVE"
    UPDATE = "UPDATE"
    NONE = "NONE"


class DependencyChange(BaseModel):
    """Structured record of an added, removed, or modified dependency."""

    model_config = ConfigDict(extra="forbid")

    package_name: str
    action: DependencyChangeAction = DependencyChangeAction.NONE
    version_spec: str = ""
    is_authorized: bool = False
    authorization_reference: str = ""
    notes: str = ""


class InterfaceChange(BaseModel):
    """Structured record of an application interface, contract, or symbol change."""

    model_config = ConfigDict(extra="forbid")

    symbol_name: str
    symbol_type: Literal["class", "function", "method", "variable", "interface", "type_alias"] = "function"
    change_type: Literal["added", "modified", "removed", "deprecated"] = "added"
    file_path: str
    signature: str = ""
    docstring: str = ""
    is_breaking: bool = False


class ToolExecutionEvidence(BaseModel):
    """Execution evidence from an isolated sandbox command or micro-tool."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    command_or_operation: str
    exit_code: int = 0
    duration_ms: float = 0.0
    output_summary: str = ""
    status: str = "SUCCESS"


class CodeSanityCheckResult(BaseModel):
    """Evidence of repository-native syntax and compiler sanity checking."""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool = True
    syntax_valid: bool = True
    compiler_passed: bool = True
    checks_run: list[str] = Field(default_factory=list)
    compiler_output: str = ""
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CodeCandidateDeliverable(BaseModel):
    """Complete sealed candidate deliverable produced by DEV-CODE for DE-04 HITL review."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    task_id: str
    workflow_id: str
    attempt_id: str = "att-1"
    component_name: str
    changed_files: list[str] = Field(default_factory=list)
    code_diffs: list[CodeDiffEntry] = Field(default_factory=list)
    source_code: dict[str, str] = Field(default_factory=dict)
    implementation_summary: str = ""
    dependency_changes: list[DependencyChange] = Field(default_factory=list)
    contract_interface_changes: list[InterfaceChange] = Field(default_factory=list)
    commands_tool_evidence: list[ToolExecutionEvidence] = Field(default_factory=list)
    ast_symbol_summary: dict[str, Any] = Field(default_factory=dict)
    sanity_check_result: CodeSanityCheckResult
    predecessor_hash: str | None = None
    input_plan_hash: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    candidate_hash: str = ""
    rejection_feedback: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)

    def canonical_bytes(self) -> bytes:
        """Return deterministic JSON-serialized byte representation of candidate code deliverable."""
        canonical_diffs = [
            {
                "file_path": d.file_path,
                "action": d.action,
                "diff_unified": d.diff_unified.strip(),
            }
            for d in sorted(self.code_diffs, key=lambda x: x.file_path)
        ]
        canonical_deps = [
            {
                "package_name": dep.package_name,
                "action": dep.action.value,
                "version_spec": dep.version_spec,
                "is_authorized": dep.is_authorized,
            }
            for dep in sorted(self.dependency_changes, key=lambda x: x.package_name)
        ]
        canonical_interfaces = [
            {
                "symbol_name": iface.symbol_name,
                "symbol_type": iface.symbol_type,
                "change_type": iface.change_type,
                "file_path": iface.file_path,
                "is_breaking": iface.is_breaking,
            }
            for iface in sorted(self.contract_interface_changes, key=lambda x: f"{x.file_path}:{x.symbol_name}")
        ]
        canonical_source = {k: v.strip() for k, v in sorted(self.source_code.items())}
        canonical_payload = {
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "attempt_id": self.attempt_id,
            "component_name": self.component_name,
            "changed_files": sorted(self.changed_files),
            "code_diffs": canonical_diffs,
            "source_code": canonical_source,
            "implementation_summary": self.implementation_summary.strip(),
            "dependency_changes": canonical_deps,
            "contract_interface_changes": canonical_interfaces,
            "predecessor_hash": self.predecessor_hash or "",
            "input_plan_hash": self.input_plan_hash or "",
            "sanity_valid": self.sanity_check_result.is_valid,
            "compiler_passed": self.sanity_check_result.compiler_passed,
        }
        return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_candidate_hash(self) -> str:
        """Compute SHA-256 tamper-evident digest of this code candidate deliverable."""
        computed = hashlib.sha256(self.canonical_bytes()).hexdigest()
        self.candidate_hash = computed
        return computed

    def to_development_deliverable(self, tenant_id: str = "default") -> DevelopmentDeliverable:
        """Convert sealed CodeCandidateDeliverable into consolidated DevelopmentDeliverable."""
        return DevelopmentDeliverable(
            deliverable_id=self.candidate_id,
            tenant_id=tenant_id,
            task_id=self.task_id,
            component_name=self.component_name,
            code_diffs=self.code_diffs,
            changed_files=self.changed_files,
            validation_findings=self.sanity_check_result.checks_run + self.sanity_check_result.warnings,
            security_checks_passed=self.sanity_check_result.is_valid,
            provenance={
                **self.provenance,
                "candidate_hash": self.candidate_hash,
                "attempt_id": self.attempt_id,
                "subagent": "DEV-CODE",
            },
        )
