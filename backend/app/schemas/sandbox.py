"""Backend-to-sandbox invocation and sanitized-result contracts."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SandboxInvocation(BaseModel):
    invocation_id: str
    capability: str
    worker_id: str
    payload: dict
    limits: dict = Field(default_factory=dict)


class SandboxResult(BaseModel):
    invocation_id: str
    status: str
    sanitized_output: dict
    telemetry: dict = Field(default_factory=dict)
