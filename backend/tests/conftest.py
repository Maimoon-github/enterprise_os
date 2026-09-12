"""Shared pytest fixtures and in-memory fakes.

Centralizing fakes here means every test file exercises the same fake
sandbox, vector store, and provenance repository shape instead of each
re-implementing its own, keeping the suite's doubles internally consistent
with the real interfaces they stand in for.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.integrations.sandbox.client import SandboxClient
from app.persistence.repositories.provenance import ProvenanceRepository, _compute_hash
from app.persistence.repositories.vector import VectorRepository
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.provenance import ProvenanceRecord
from app.schemas.sandbox import SandboxInvocationMandate, SandboxResult
from app.schemas.task_state import CanonicalTaskState, TaskStatus


class FakeSandboxClient(SandboxClient):
    """A drop-in stand-in for ``SandboxClient`` that never touches agent_sandbox."""

    def __init__(self, *, should_fail: bool = False) -> None:
        super().__init__(settings=None)
        self.should_fail = should_fail
        self.invocations: list[SandboxInvocationMandate] = []

    async def invoke(self, mandate: SandboxInvocationMandate) -> SandboxResult:
        self.invocations.append(mandate)
        if self.should_fail:
            return SandboxResult(
                task_id=mandate.task_id,
                capability=mandate.capability,
                success=False,
                error="simulated sandbox failure",
            )
        return SandboxResult(
            task_id=mandate.task_id,
            capability=mandate.capability,
            success=True,
            sanitized_output={
                "objective": mandate.payload.get("objective", "unknown"),
                "result": f"{mandate.capability.value} completed for {mandate.task_id}",
            },
        )


class FakeVectorRepository(VectorRepository):
    """A drop-in stand-in for ``VectorRepository`` satisfying the retriever protocol."""

    def __init__(self, documents: list[dict[str, Any]] | None = None) -> None:
        super().__init__(session_factory=None)  # type: ignore[arg-type]
        self._documents = documents or []

    def seed(self, *, tenant_id: str, text: str, source: str = "test") -> None:
        self._documents.append(
            {
                "doc_id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "text": text,
                "source": source,
                "retrieved_at": datetime.now(UTC),
                "score": 0.9,
            }
        )

    async def index_document(
        self,
        *,
        doc_id: str,
        tenant_id: str,
        text: str,
        source: str,
    ) -> None:
        self._documents.append(
            {
                "doc_id": doc_id,
                "tenant_id": tenant_id,
                "text": text,
                "source": source,
                "retrieved_at": datetime.now(UTC),
                "score": 0.9,
            }
        )

    async def similarity_search(
        self, *, tenant_id: str, query: str, top_k: int
    ) -> list[dict[str, Any]]:
        matches = [doc for doc in self._documents if doc["tenant_id"] == tenant_id]
        return matches[:top_k]


class FakeProvenanceRepository(ProvenanceRepository):
    """An in-memory ``ProvenanceRepository`` that never touches a real database."""

    def __init__(self) -> None:
        super().__init__(session_factory=None)  # type: ignore[arg-type]
        self._chains: dict[str, list[ProvenanceRecord]] = {}

    async def _latest(self, tenant_id: str) -> ProvenanceRecord | None:
        records = self._chains.get(tenant_id, [])
        return records[-1] if records else None

    async def append(
        self, *, tenant_id: str, entity_id: str, activity: str, agent: str
    ) -> ProvenanceRecord:
        occurred_at = datetime.now(UTC)
        latest = await self._latest(tenant_id)
        prev_hash = latest.record_hash if latest else None
        record = ProvenanceRecord(
            record_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            entity_id=entity_id,
            activity=activity,
            agent=agent,
            occurred_at=occurred_at,
            prev_record_hash=prev_hash,
            record_hash=_compute_hash(prev_hash, entity_id, activity, agent, occurred_at),
        )
        self._chains.setdefault(tenant_id, []).append(record)
        return record

    async def chain(self, tenant_id: str) -> list[ProvenanceRecord]:
        return list(self._chains.get(tenant_id, []))


@pytest.fixture
def ed25519_keypair() -> tuple[Ed25519PrivateKey, str]:
    """Return a fresh (private_key, public_key_pem) pair for signature tests."""

    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")
    return private_key, public_pem


@pytest.fixture
def sample_tenant_scope() -> TenantScope:
    return TenantScope(
        tenant_id="acme", brand_ids=["brand-1"], allowed_channels=["meta", "instagram"]
    )


@pytest.fixture
def sample_directive(sample_tenant_scope: TenantScope) -> Directive:
    return Directive(
        directive_id=str(uuid.uuid4()),
        tenant_id="acme",
        objective="Grow qualified pipeline for the summer campaign.",
        budget_cap=5000.0,
        risk_ceiling=RiskLevel.MEDIUM,
        scope=sample_tenant_scope,
    )


@pytest.fixture
def sample_task(sample_directive: Directive) -> CanonicalTaskState:
    return CanonicalTaskState(
        task_id=str(uuid.uuid4()),
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.PENDING,
    )


@pytest.fixture
def fresh_document() -> dict[str, Any]:
    return {
        "doc_id": "doc-1",
        "tenant_id": "acme",
        "text": "summer campaign performance summary",
        "source": "test",
        "retrieved_at": datetime.now(UTC) - timedelta(days=1),
    }


@pytest.fixture
def stale_document() -> dict[str, Any]:
    return {
        "doc_id": "doc-2",
        "tenant_id": "acme",
        "text": "outdated report",
        "source": "test",
        "retrieved_at": datetime.now(UTC) - timedelta(days=365),
    }
