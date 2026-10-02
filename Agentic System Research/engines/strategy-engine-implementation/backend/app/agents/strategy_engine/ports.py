"""Trusted host ports; implemented by IE/PAB and the append-only audit service.

Host adapters must authenticate the caller and enforce policy; a schema or hash
is not authorization. No persistence client is exposed to the worker.
"""
from datetime import datetime
from typing import Protocol

from app.schemas.strategy import (AuditEvent, AuditReceipt, AuthorizationReceipt,
    ContextIngestion, ContextRequest, EvidenceEnvelope, SubmissionReceipt, TaskGrant)


class IntelligenceEnginePort(Protocol):
    async def authorize(self, grant: TaskGrant) -> AuthorizationReceipt:
        """Verify signed parent chain, tenant, revocation, expiry and attenuation."""
        ...

    async def request_context(self, request: ContextRequest) -> ContextIngestion:
        """Return the same durable, authorized snapshot on retry of the same grant."""
        ...

    async def submit(self, envelope: EvidenceEnvelope) -> SubmissionReceipt:
        """Atomically persist artifact/proposed CTS delta; deduplicate artifact_id.

        This is a proposal only. No spend, publishing, or deploy authorization.
        """
        ...


class AuditPort(Protocol):
    async def append(self, event: AuditEvent) -> AuditReceipt:
        """Durably append complete payload and its PROV relations.

        Enforce uniqueness(event_id), reject different bytes for an existing ID,
        enforce previous_hash per run, serialize concurrent appends, and retain
        immutable payloads. Retries of identical bytes return the same receipt.
        """
        ...


class Clock(Protocol):
    def __call__(self) -> datetime: ...


class StrategyWorker(Protocol):
    """Explicit standard worker interface; bind to BaseAgent in the host adapter."""
    worker_id: str
    async def execute(self, grant: TaskGrant) -> EvidenceEnvelope: ...
