"""Typed contracts for W_DEV (Development Engine) core, requests, and deliverables."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.agent_contracts import (
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
