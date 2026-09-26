"""Backend-to-sandbox invocation mandates and sanitized-result contracts.

These contracts define the typed interface between the backend/workers and
the sandbox execution boundary, enforcing least privilege, execution limits,
network policy, and structured sanitization.
"""

from __future__ import annotations

import ipaddress
import re
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.governance import WorkerRole


class SandboxCapability(StrEnum):
    """The seven sandbox capabilities available to bounded workers."""

    CODE = "S_CODE"
    ALLOC = "S_ALLOC"
    COPY = "S_COPY"
    VAL = "S_VAL"
    COMP = "s-comp"
    PARSE = "S_PARSE"
    ATTR = "S_ATTR"

    @classmethod
    def _missing_(cls, value: object) -> SandboxCapability | None:
        if isinstance(value, str):
            val_norm = value.strip().upper()
            if val_norm in ("S_SCRAPE", "SCRAPE", "S_COMP"):
                return cls.COMP
        return super()._missing_(value)


# Explicit backward-compatibility alias; never emitted or documented as canonical
SandboxCapability.SCRAPE = SandboxCapability.COMP


class NetworkPolicy(StrEnum):
    """Network egress policy enforced on sandbox execution."""

    DISABLED = "disabled"
    CONTROLLED = "controlled"
    ALLOWLIST = "allowlist"


class ResourceLimits(BaseModel):
    """Resource bounds applied to a single sandbox invocation."""

    timeout_seconds: int = Field(default=120, ge=1, le=600)
    memory_mb: int = Field(default=1024, ge=128, le=8192)
    cpu_cores: float = Field(default=1.0, ge=0.1, le=4.0)


class SandboxExecutionStatus(StrEnum):
    """Execution lifecycle outcome from the sandbox boundary."""

    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "metadata.google.internal",
    "instance-data",
    "169.254.169.254",
    "host.docker.internal",
    "metadata",
    "enterprise-db",
    "enterprise-redis",
    "enterprise-rag",
    "enterprise-mcp",
    "enterprise-cms",
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
})


class SandboxEgressGrant(BaseModel):
    """Explicit, tenant-scoped, task-scoped, and time-bounded network egress authorization."""

    grant_id: str = Field(default_factory=lambda: f"egress-{uuid.uuid4()}")
    tenant_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    specialist_id: str = ""
    stage_attempt_id: str = ""
    worker_id: str = "W_COMP"
    worker_role: WorkerRole = WorkerRole.COMPETITOR_INTEL
    capability: SandboxCapability = SandboxCapability.COMP
    allowed_domains: list[str] = Field(..., min_length=1)
    allowed_ports: list[int] = Field(default_factory=lambda: [80, 443])
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    policy_version: str = "v1"

    @field_validator("allowed_domains")
    @classmethod
    def validate_domains(cls, domains: list[str]) -> list[str]:
        cleaned: list[str] = []
        for domain in domains:
            d = domain.strip().lower()
            if d == "*" or d == "*.*":
                raise ValueError("Universal wildcard '*' is not permitted in production egress allowlist.")
            if d in _BLOCKED_HOSTNAMES or any(d.startswith(p) for p in ("enterprise-", "169.254.", "127.", "10.", "192.168.")):
                raise ValueError(f"Prohibited private/internal host in egress allowlist: '{d}'")
            try:
                ip = ipaddress.ip_address(d)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    raise ValueError(f"Private or loopback IP '{d}' is forbidden in egress allowlist.")
            except ValueError as exc:
                if "forbidden" in str(exc):
                    raise
            cleaned.append(d)
        return cleaned

    @field_validator("allowed_ports")
    @classmethod
    def validate_ports(cls, ports: list[int]) -> list[int]:
        for port in ports:
            if not (1 <= port <= 65535):
                raise ValueError(f"Invalid port: {port}")
            if port not in (80, 443, 8080, 8443):
                # Standard web ports allowed by default; arbitrary internal ports denied
                pass
        return ports

    def is_expired(self, at: datetime | None = None) -> bool:
        current_time = at or datetime.now(UTC)
        return current_time > self.expires_at

    def is_destination_allowed(self, target: str, port: int | None = None) -> tuple[bool, str]:
        """Verify whether a target URL or domain+port is authorized under this grant."""
        if self.is_expired():
            return False, f"Egress grant '{self.grant_id}' has expired."

        # Parse target into hostname and target port
        raw_target = target.strip()
        if "://" in raw_target:
            parsed = urlparse(raw_target)
            host = parsed.hostname or ""
            target_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        else:
            if ":" in raw_target and not raw_target.startswith("["):
                parts = raw_target.split(":", 1)
                host = parts[0]
                try:
                    target_port = int(parts[1])
                except ValueError:
                    return False, f"Invalid port in target: '{raw_target}'"
            else:
                host = raw_target
                target_port = port or 443

        host = host.strip().lower()

        # SSRF Checks
        if host in _BLOCKED_HOSTNAMES or any(host.startswith(p) for p in ("enterprise-", "169.254.", "127.", "10.", "192.168.")):
            return False, f"Access to private/metadata host '{host}' is strictly blocked."

        if target_port in (5432, 6379, 27017, 9200):
            return False, f"Port {target_port} is reserved for internal enterprise infrastructure and strictly forbidden."

        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False, f"Access to private/loopback/link-local IP '{host}' is strictly blocked."
        except ValueError:
            pass

        # Validate Port
        if target_port not in self.allowed_ports:
            return False, f"Port {target_port} is not in allowed ports {self.allowed_ports}."

        # Validate Domain Match (Exact or Wildcard)
        for allowed in self.allowed_domains:
            allowed = allowed.lower().strip()
            if allowed.startswith("*."):
                suffix = allowed[2:]
                if host == suffix or host.endswith("." + suffix):
                    return True, "Authorized"
            elif host == allowed:
                return True, "Authorized"

        return False, f"Domain '{host}' is not in approved allowlist for grant '{self.grant_id}'."


class SandboxInvocationMandate(BaseModel):
    """A single, explicit, typed request to execute one sandbox capability."""

    execution_id: str = Field(default_factory=lambda: f"exec-{uuid.uuid4()}")
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stage_attempt_id: str = Field(default_factory=lambda: f"att-{uuid.uuid4().hex[:8]}")
    worker_role: WorkerRole | None = None
    worker_id: str = ""
    tenant_id: str = "default"
    capability: SandboxCapability
    specialist_agent: str = ""
    specialist_id: str = ""
    operation: str = "default"
    payload: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    resource_limits: ResourceLimits = Field(default_factory=ResourceLimits)
    network_policy: NetworkPolicy = NetworkPolicy.DISABLED
    egress_grant: SandboxEgressGrant | None = None
    timeout_seconds: int = Field(default=120, ge=1)
    stop_rules: list[str] = Field(default_factory=list)
    expected_output_schema: dict[str, Any] = Field(default_factory=dict)
    working_directory_policy: str = "ephemeral"
    artifact_policy: str = "controlled"
    provenance_context: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_mandate_integrity(self) -> SandboxInvocationMandate:
        """Ensure network policy, specialist identity, and egress grant consistency."""
        if not self.specialist_id:
            self.specialist_id = self.specialist_agent or self.capability.value
        if not self.worker_id and self.worker_role is not None:
            self.worker_id = self.worker_role.value

        if self.egress_grant is not None:
            if self.network_policy == NetworkPolicy.DISABLED:
                raise ValueError("Egress grant cannot be attached when network_policy is DISABLED.")
            if self.egress_grant.tenant_id != self.tenant_id:
                raise ValueError(
                    f"Egress grant tenant '{self.egress_grant.tenant_id}' does not match mandate tenant '{self.tenant_id}'."
                )
            if self.egress_grant.task_id != self.task_id:
                raise ValueError(
                    f"Egress grant task '{self.egress_grant.task_id}' does not match mandate task '{self.task_id}'."
                )
            if self.worker_role is not None and self.egress_grant.worker_role != self.worker_role:
                raise ValueError(
                    f"Egress grant worker '{self.egress_grant.worker_role}' does not match mandate worker '{self.worker_role}'."
                )
            if self.egress_grant.specialist_id and self.specialist_id and self.egress_grant.specialist_id != self.specialist_id:
                raise ValueError(
                    f"Egress grant specialist '{self.egress_grant.specialist_id}' does not match mandate specialist '{self.specialist_id}'."
                )
            if self.specialist_id and not self.egress_grant.specialist_id:
                self.egress_grant.specialist_id = self.specialist_id
            if self.stage_attempt_id and not self.egress_grant.stage_attempt_id:
                self.egress_grant.stage_attempt_id = self.stage_attempt_id
        return self


class SandboxResult(BaseModel):
    """A sanitized, typed result returned from the sandbox boundary."""

    execution_id: str = Field(default_factory=lambda: f"exec-{uuid.uuid4()}")
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    worker_role: WorkerRole | None = None
    worker_id: str = ""
    specialist_id: str = ""
    capability: SandboxCapability
    status: SandboxExecutionStatus = SandboxExecutionStatus.COMPLETED
    success: bool
    sanitized_output: dict[str, str] = Field(default_factory=dict)
    structured_output: dict[str, Any] = Field(default_factory=dict)
    validated_findings: list[str] = Field(default_factory=list)
    confidence_score: float = 1.0
    generated_diff: str = ""
    stdout: str = ""
    sanitized_stderr: str = ""
    generated_artifacts: list[str] = Field(default_factory=list)
    artifact_references: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    validation_results: dict[str, Any] = Field(default_factory=dict)
    execution_duration_ms: float = 0.0
    resource_usage: dict[str, Any] = Field(default_factory=dict)
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


# ===========================================================================
# Sandbox Control Plane Contracts (DE-03)
# ===========================================================================

class SandboxLifecycleState(StrEnum):
    """Authoritative lifecycle state of an isolated sandbox instance."""

    PROVISIONING = "PROVISIONING"
    VALIDATED = "VALIDATED"
    RUNNING = "RUNNING"
    RESULT_SEALED = "RESULT_SEALED"
    TERMINATED = "TERMINATED"
    DESTROYED = "DESTROYED"
    FAILED = "FAILED"


class SandboxIdentity(BaseModel):
    """Authoritative binding of a sandbox to tenant, region, engine, task, step, attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(..., min_length=1)
    work_region: str = Field(default="primary")
    engine_id: str = Field(default="W_DEV")
    specialist_id: str = ""
    task_id: str = Field(..., min_length=1)
    step_id: str = Field(..., min_length=1)
    attempt_id: str = Field(..., min_length=1)
    sandbox_id: str = Field(default_factory=lambda: f"sbx-{uuid.uuid4().hex[:12]}")

    @classmethod
    def generate(
        cls,
        tenant_id: str,
        task_id: str,
        step_id: str,
        attempt_id: str,
        work_region: str = "primary",
        engine_id: str = "W_DEV",
        specialist_id: str = "",
    ) -> SandboxIdentity:
        sbx_id = f"sbx-{tenant_id}-{engine_id}-{task_id[:8]}-{step_id[:8]}-{attempt_id[:8]}-{uuid.uuid4().hex[:6]}"
        return cls(
            tenant_id=tenant_id,
            work_region=work_region,
            engine_id=engine_id,
            specialist_id=specialist_id,
            task_id=task_id,
            step_id=step_id,
            attempt_id=attempt_id,
            sandbox_id=sbx_id,
        )


class SandboxFilesystemPolicy(BaseModel):
    """Filesystem isolation, ephemeral workspace mounts, and path constraints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace_mount_type: str = "ephemeral_tmpfs"
    max_workspace_size_mb: int = Field(default=2048, ge=64, le=10240)
    noexec_tmp: bool = True
    nosuid_tmp: bool = True
    read_only_mounts: tuple[str, ...] = ("/home/gem/skills",)
    allowed_write_paths: tuple[str, ...] = ("/workspace", "/tmp", "/run")
    forbidden_host_paths: tuple[str, ...] = (
        "/",
        "/var/run/docker.sock",
        "/etc",
        "/proc/sys",
        "/sys",
    )


class SandboxNetworkPolicyConfig(BaseModel):
    """Egress policy configuration and anti-SSRF protections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_mode: str = "deny_all"  # "deny_all" | "allowlist"
    proxy_endpoint: str = "http://aio-egress-proxy:8118"
    allowed_domains: tuple[str, ...] = ()
    allowed_ports: tuple[int, ...] = (80, 443)
    blocked_subnets: tuple[str, ...] = (
        "169.254.169.254/32",  # Cloud instance metadata
        "127.0.0.0/8",         # Host loopback
        "10.0.0.0/8",          # Private network
        "172.16.0.0/12",       # Docker bridge network
        "192.168.0.0/16",      # Local network
    )
    blocked_services: tuple[str, ...] = (
        "localhost",
        "metadata.google.internal",
        "instance-data",
        "169.254.169.254",
        "host.docker.internal",
        "enterprise-db",
        "enterprise-redis",
    )


class SandboxResourceLimits(BaseModel):
    """Extended resource and security boundary specifications."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    timeout_seconds: int = Field(default=120, ge=1, le=600)
    memory_mb: int = Field(default=1024, ge=128, le=8192)
    cpu_cores: float = Field(default=1.0, ge=0.1, le=4.0)
    pids_limit: int = Field(default=1024, ge=32, le=4096)
    no_new_privileges: bool = True
    cap_drop: tuple[str, ...] = ("ALL",)
    seccomp_profile: str = "worker-seccomp.json"
    run_as_user: str = "1000:1000"


class SandboxCapabilityGrant(BaseModel):
    """Explicit per-attempt tool and capability authorization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lease_id: str = Field(..., min_length=1)
    subagent_id: str = Field(..., min_length=1)
    capability: SandboxCapability = SandboxCapability.CODE
    allowed_tools: tuple[str, ...] = ("ast_parser", "code_linter", "diff_generator")
    allowed_operations: tuple[str, ...] = (
        "parse_ast",
        "lint",
        "generate_diff",
        "execute_code",
        "validate_syntax",
        "default",
    )


class SealedSandboxOutput(BaseModel):
    """Immutable cryptographically sealed outputs extracted from sandbox before teardown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sandbox_id: str
    task_id: str
    step_id: str
    attempt_id: str
    state: SandboxLifecycleState = SandboxLifecycleState.RESULT_SEALED
    artifacts: dict[str, str] = Field(default_factory=dict)
    artifact_hashes: dict[str, str] = Field(
        default_factory=dict, description="SHA-256 digests of all outputs"
    )
    generated_diff: str = ""
    diff_hash: str = ""
    sanitized_output: dict[str, str] = Field(default_factory=dict)
    structured_output: dict[str, Any] = Field(default_factory=dict)
    sealed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    signature: str | None = None