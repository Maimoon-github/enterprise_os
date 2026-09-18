"""Typed contracts for W_DEV (Development Engine) core, requests, and deliverables."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.agent_contracts import (
    CodeDiffEntry,
    DevelopmentDeliverable,
    EvidenceEnvelope,
    TaskGrant,
)
from app.schemas.governance import WorkerRole
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
            raise ValueError(
                f"Task grant expired at {val_utc.isoformat()} (current time: {now.isoformat()})."
            )
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
    symbol_type: Literal["class", "function", "method", "variable", "interface", "type_alias"] = (
        "function"
    )
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
            for iface in sorted(
                self.contract_interface_changes, key=lambda x: f"{x.file_path}:{x.symbol_name}"
            )
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
            validation_findings=self.sanity_check_result.checks_run
            + self.sanity_check_result.warnings,
            security_checks_passed=self.sanity_check_result.is_valid,
            provenance={
                **self.provenance,
                "candidate_hash": self.candidate_hash,
                "attempt_id": self.attempt_id,
                "subagent": "DEV-CODE",
            },
        )


class VerificationVerdict(StrEnum):
    """Machine determination verdict for DEV-VERIFY."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    BLOCKED = "BLOCKED"


class CheckOutcome(StrEnum):
    """Individual verification check outcome."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


class VerificationCheckResult(BaseModel):
    """Execution outcome of a single repository-native verification check."""

    model_config = ConfigDict(extra="forbid")

    check_id: str
    check_type: Literal[
        "environment",
        "build",
        "lint",
        "format",
        "type_check",
        "unit_test",
        "integration_test",
        "coverage",
    ]
    outcome: CheckOutcome
    command_or_operation: str
    exit_code: int = 0
    duration_ms: float = 0.0
    output_summary: str = ""
    stdout: str = ""
    stderr: str = ""
    error_count: int = 0
    warning_count: int = 0
    failure_reasons: list[str] = Field(default_factory=list)
    is_mandatory: bool = True


class CoverageReport(BaseModel):
    """Detailed automated test coverage analysis."""

    model_config = ConfigDict(extra="forbid")

    line_coverage_pct: float = 0.0
    branch_coverage_pct: float = 0.0
    total_statements: int = 0
    covered_statements: int = 0
    missing_lines_by_file: dict[str, list[int]] = Field(default_factory=dict)
    coverage_threshold_met: bool = True
    minimum_required_pct: float = 80.0


class TestTotals(BaseModel):
    """Consolidated test runner results."""

    __test__ = False

    model_config = ConfigDict(extra="forbid")

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errored: int = 0
    total: int = 0
    duration_s: float = 0.0


class VerificationDossier(BaseModel):
    """Tamper-evident verification dossier produced by DEV-VERIFY."""

    model_config = ConfigDict(extra="forbid")

    dossier_id: str
    task_id: str
    workflow_id: str
    candidate_hash: str
    target_candidate_id: str
    component_name: str
    verdict: VerificationVerdict
    remediation_step: str | None = None
    checks: list[VerificationCheckResult] = Field(default_factory=list)
    test_totals: TestTotals = Field(default_factory=TestTotals)
    coverage_report: CoverageReport | None = None
    evidence_envelopes: list[EvidenceEnvelope] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    dossier_hash: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def canonical_bytes(self) -> bytes:
        """Deterministic byte representation of verification dossier."""
        canonical_checks = [
            {
                "check_id": c.check_id,
                "check_type": c.check_type,
                "outcome": c.outcome.value,
                "command_or_operation": c.command_or_operation,
                "exit_code": c.exit_code,
                "error_count": c.error_count,
                "warning_count": c.warning_count,
                "failure_reasons": sorted(c.failure_reasons),
                "is_mandatory": c.is_mandatory,
            }
            for c in sorted(self.checks, key=lambda x: x.check_id)
        ]
        canonical_payload = {
            "dossier_id": self.dossier_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "candidate_hash": self.candidate_hash,
            "target_candidate_id": self.target_candidate_id,
            "component_name": self.component_name,
            "verdict": self.verdict.value,
            "remediation_step": self.remediation_step or "",
            "checks": canonical_checks,
            "test_totals": {
                "passed": self.test_totals.passed,
                "failed": self.test_totals.failed,
                "skipped": self.test_totals.skipped,
                "errored": self.test_totals.errored,
                "total": self.test_totals.total,
            },
            "coverage_threshold_met": self.coverage_report.coverage_threshold_met
            if self.coverage_report
            else True,
            "line_coverage_pct": round(self.coverage_report.line_coverage_pct, 2)
            if self.coverage_report
            else 0.0,
        }
        return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_dossier_hash(self) -> str:
        """Compute SHA-256 digest of this verification dossier."""
        digest = hashlib.sha256(self.canonical_bytes()).hexdigest()
        self.dossier_hash = digest
        return digest

    def is_acceptable_for_dev_sec(self) -> bool:
        """Verify whether this dossier authorizes advancement to DEV-SEC."""
        return self.verdict == VerificationVerdict.PASS


class SecuritySeverity(StrEnum):
    """Vulnerability and risk severity classification for DEV-SEC."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class SecurityCategory(StrEnum):
    """Categorization of security review findings."""

    SAST = "SAST"
    SECRET = "SECRET"
    SCA = "SCA"
    CONFIG = "CONFIG"
    PERMISSION = "PERMISSION"
    AST_PATTERN = "AST_PATTERN"


class SecurityFinding(BaseModel):
    """An individual security, vulnerability, or compliance finding."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    rule_id: str
    category: SecurityCategory
    severity: SecuritySeverity
    title: str
    description: str
    file_path: str
    line_number: int | None = None
    code_snippet: str = ""
    remediation_target: str = "DEV-CODE"
    is_hard_block: bool = False
    cve_id: str | None = None
    cwe_id: str | None = None


class SecurityVerdict(StrEnum):
    """Machine policy determination verdict for DEV-SEC."""

    PASS = "PASS"
    DENY = "DENY"
    ERROR = "ERROR"


class SecurityDossier(BaseModel):
    """Tamper-evident security audit dossier produced by DEV-SEC."""

    model_config = ConfigDict(extra="forbid")

    dossier_id: str
    task_id: str
    workflow_id: str
    candidate_hash: str
    target_candidate_id: str
    component_name: str
    verdict: SecurityVerdict
    scanners_run: list[str] = Field(default_factory=list)
    scanner_versions: dict[str, str] = Field(default_factory=dict)
    findings: list[SecurityFinding] = Field(default_factory=list)
    hard_block_count: int = 0
    remediation_targets: list[str] = Field(default_factory=list)
    evidence_envelopes: list[EvidenceEnvelope] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    dossier_hash: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def canonical_bytes(self) -> bytes:
        """Deterministic byte representation of security dossier."""
        canonical_findings = [
            {
                "finding_id": f.finding_id,
                "rule_id": f.rule_id,
                "category": f.category.value,
                "severity": f.severity.value,
                "file_path": f.file_path,
                "line_number": f.line_number or 0,
                "is_hard_block": f.is_hard_block,
                "remediation_target": f.remediation_target,
            }
            for f in sorted(self.findings, key=lambda x: x.finding_id)
        ]
        canonical_payload = {
            "dossier_id": self.dossier_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "candidate_hash": self.candidate_hash,
            "target_candidate_id": self.target_candidate_id,
            "component_name": self.component_name,
            "verdict": self.verdict.value,
            "scanners_run": sorted(self.scanners_run),
            "findings": canonical_findings,
            "hard_block_count": self.hard_block_count,
            "remediation_targets": sorted(self.remediation_targets),
        }
        return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_dossier_hash(self) -> str:
        """Compute SHA-256 digest of this security dossier."""
        digest = hashlib.sha256(self.canonical_bytes()).hexdigest()
        self.dossier_hash = digest
        return digest

    def is_acceptable_for_release(self) -> bool:
        """Verify whether this dossier authorizes progression to DEV-REL."""
        return self.verdict == SecurityVerdict.PASS and self.hard_block_count == 0


class CycloneDxComponent(BaseModel):
    """Component entry within a CycloneDX v1.5 Software Bill of Materials."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    type: str = "library"
    purl: str = ""
    hashes: dict[str, str] = Field(default_factory=dict)
    licenses: list[str] = Field(default_factory=list)


class CycloneDxSbom(BaseModel):
    """CycloneDX v1.5 Software Bill of Materials."""

    model_config = ConfigDict(extra="forbid")

    bomFormat: str = "CycloneDX"
    specVersion: str = "1.5"
    serialNumber: str
    version: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)
    components: list[CycloneDxComponent] = Field(default_factory=list)
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    sbom_hash: str = ""

    def canonical_bytes(self) -> bytes:
        """Deterministic byte representation of CycloneDX SBOM."""
        canonical_components = [
            {
                "name": c.name,
                "version": c.version,
                "type": c.type,
                "purl": c.purl,
                "hashes": dict(sorted(c.hashes.items())),
            }
            for c in sorted(self.components, key=lambda x: x.name)
        ]
        canonical_payload = {
            "bomFormat": self.bomFormat,
            "specVersion": self.specVersion,
            "serialNumber": self.serialNumber,
            "version": self.version,
            "components": canonical_components,
        }
        return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_sbom_hash(self) -> str:
        """Compute SHA-256 digest of this SBOM."""
        digest = hashlib.sha256(self.canonical_bytes()).hexdigest()
        self.sbom_hash = digest
        return digest


class DeploymentManifest(BaseModel):
    """Content-addressable deployment specification for target runtime environment."""

    model_config = ConfigDict(extra="forbid")

    manifest_id: str
    component_name: str
    version: str = "1.0.0"
    runtime: str = "python:3.11-slim"
    entrypoint: str = "main.py"
    environment_variables: dict[str, str] = Field(default_factory=dict)
    healthcheck_endpoint: str = "/health"
    resource_limits: dict[str, str] = Field(
        default_factory=lambda: {"cpu": "1.0", "memory": "1Gi"}
    )
    ingress_route: str = ""
    manifest_hash: str = ""

    def canonical_bytes(self) -> bytes:
        """Deterministic byte representation of deployment manifest."""
        canonical_payload = {
            "manifest_id": self.manifest_id,
            "component_name": self.component_name,
            "version": self.version,
            "runtime": self.runtime,
            "entrypoint": self.entrypoint,
            "environment_variables": dict(sorted(self.environment_variables.items())),
            "healthcheck_endpoint": self.healthcheck_endpoint,
            "resource_limits": dict(sorted(self.resource_limits.items())),
            "ingress_route": self.ingress_route,
        }
        return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_manifest_hash(self) -> str:
        """Compute SHA-256 digest of this deployment manifest."""
        digest = hashlib.sha256(self.canonical_bytes()).hexdigest()
        self.manifest_hash = digest
        return digest


class MigrationInstruction(BaseModel):
    """Validated database/CMS schema migration step and dry-run evidence."""

    model_config = ConfigDict(extra="forbid")

    step_number: int
    operation: str
    model_name: str
    dry_run_passed: bool = True
    sql_or_schema_change: str = ""


class RollbackManifest(BaseModel):
    """Deterministic rollback procedure and instructions for release reversal."""

    model_config = ConfigDict(extra="forbid")

    rollback_id: str
    target_release_id: str
    previous_stable_version: str
    rollback_strategy: str = "BLUE_GREEN_DRAIN"
    revert_steps: list[str] = Field(default_factory=list)
    migration_revert_instructions: list[MigrationInstruction] = Field(default_factory=list)
    automated_verification_steps: list[str] = Field(default_factory=list)
    rollback_hash: str = ""

    def canonical_bytes(self) -> bytes:
        """Deterministic byte representation of rollback manifest."""
        canonical_payload = {
            "rollback_id": self.rollback_id,
            "target_release_id": self.target_release_id,
            "previous_stable_version": self.previous_stable_version,
            "rollback_strategy": self.rollback_strategy,
            "revert_steps": self.revert_steps,
        }
        return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_rollback_hash(self) -> str:
        """Compute SHA-256 digest of this rollback manifest."""
        digest = hashlib.sha256(self.canonical_bytes()).hexdigest()
        self.rollback_hash = digest
        return digest


class ReleaseArtifact(BaseModel):
    """An individual packaged deliverable artifact with cryptographic digest."""

    model_config = ConfigDict(extra="forbid")

    artifact_name: str
    file_path: str
    sha256: str
    size_bytes: int
    media_type: str = "application/octet-stream"


class ReleaseCandidateDeliverable(BaseModel):
    """Immutable, content-addressable release candidate package produced by DEV-REL."""

    model_config = ConfigDict(extra="forbid")

    release_id: str
    task_id: str
    workflow_id: str
    security_dossier_hash: str
    candidate_hash: str
    component_name: str
    version: str = "1.0.0"
    release_artifacts: list[ReleaseArtifact] = Field(default_factory=list)
    artifact_digests: dict[str, str] = Field(default_factory=dict)
    sbom: CycloneDxSbom
    deployment_manifest: DeploymentManifest
    rollback_manifest: RollbackManifest
    migration_dry_run_evidence: list[MigrationInstruction] = Field(default_factory=list)
    attestation_statement: dict[str, Any] | None = None
    evidence_envelopes: list[EvidenceEnvelope] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    release_hash: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def canonical_bytes(self) -> bytes:
        """Deterministic byte representation of release candidate package."""
        canonical_artifacts = [
            {
                "artifact_name": a.artifact_name,
                "file_path": a.file_path,
                "sha256": a.sha256,
                "size_bytes": a.size_bytes,
            }
            for a in sorted(self.release_artifacts, key=lambda x: x.artifact_name)
        ]
        canonical_payload = {
            "release_id": self.release_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "security_dossier_hash": self.security_dossier_hash,
            "candidate_hash": self.candidate_hash,
            "component_name": self.component_name,
            "version": self.version,
            "release_artifacts": canonical_artifacts,
            "artifact_digests": dict(sorted(self.artifact_digests.items())),
            "sbom_hash": self.sbom.sbom_hash or self.sbom.compute_sbom_hash(),
            "deployment_manifest_hash": (
                self.deployment_manifest.manifest_hash
                or self.deployment_manifest.compute_manifest_hash()
            ),
            "rollback_manifest_hash": (
                self.rollback_manifest.rollback_hash
                or self.rollback_manifest.compute_rollback_hash()
            ),
        }
        return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_release_hash(self) -> str:
        """Compute SHA-256 digest of this release candidate package."""
        digest = hashlib.sha256(self.canonical_bytes()).hexdigest()
        self.release_hash = digest
        return digest


# Canonical alias
ReleaseDossier = ReleaseCandidateDeliverable

