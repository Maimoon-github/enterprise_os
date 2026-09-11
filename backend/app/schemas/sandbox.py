"""Backend-to-sandbox invocation mandates and sanitized-result contracts.

These contracts intentionally expose no internal detail of the existing
``agent_sandbox`` SDK; they define only what the backend sends in and
receives back.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SandboxCapability(StrEnum):
    """The seven sandbox capabilities available to bounded workers."""

    CODE = "S_CODE"
    ALLOC = "S_ALLOC"
    COPY = "S_COPY"
    VAL = "S_VAL"
    SCRAPE = "S_SCRAPE"
    PARSE = "S_PARSE"
    ATTR = "S_ATTR"


class SandboxInvocationMandate(BaseModel):
    """A single, explicit request to execute one sandbox capability."""

    task_id: str
    capability: SandboxCapability
    payload: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=120, ge=1)


class SandboxResult(BaseModel):
    """A sanitized result returned from the sandbox boundary."""

    task_id: str
    capability: SandboxCapability
    success: bool
    sanitized_output: dict[str, str] = Field(default_factory=dict)
    error: str | None = None