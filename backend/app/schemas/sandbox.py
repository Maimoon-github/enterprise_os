"""Backend-to-sandbox invocation mandates and sanitized-result contracts.

These contracts define the typed interface between the backend/workers and
the sandbox execution boundary, enforcing least privilege, execution limits,
network policy, and structured sanitization.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.governance import WorkerRole


class SandboxCapability(StrEnum):
    """The seven sandbox capabilities available to bounded workers."""

    CODE = "S_CODE"
    ALLOC = "S_ALLOC"
    COPY = "S_COPY"
    VAL = "S_VAL"
    SCRAPE = "S_SCRAPE"
    PARSE = "S_PARSE"
    ATTR = "S_ATTR"


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


class SandboxInvocationMandate(BaseModel):
    """A single, explicit, typed request to execute one sandbox capability."""

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    worker_role: WorkerRole | None = None
    tenant_id: str = "default"
    capability: SandboxCapability
    specialist_agent: str = ""
    operation: str = "default"
    payload: dict[str, str] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    resource_limits: ResourceLimits = Field(default_factory=ResourceLimits)
    network_policy: NetworkPolicy = NetworkPolicy.DISABLED
    timeout_seconds: int = Field(default=120, ge=1)
    working_directory_policy: str = "ephemeral"
    artifact_policy: str = "controlled"
    provenance_context: dict[str, str] = Field(default_factory=dict)


class SandboxResult(BaseModel):
    """A sanitized, typed result returned from the sandbox boundary."""

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    worker_role: WorkerRole | None = None
    capability: SandboxCapability
    status: SandboxExecutionStatus = SandboxExecutionStatus.COMPLETED
    success: bool
    sanitized_output: dict[str, str] = Field(default_factory=dict)
    structured_output: dict[str, Any] = Field(default_factory=dict)
    stdout: str = ""
    sanitized_stderr: str = ""
    generated_artifacts: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    validation_results: dict[str, Any] = Field(default_factory=dict)
    execution_duration_ms: float = 0.0
    resource_usage: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)
    error: str | None = None