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
from app.persistence.repositories.provenance import (
    ProvenanceRepository,
    _compute_hash,
    _compute_metadata_hash,
)
from app.persistence.repositories.vector import VectorRepository
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.provenance import ProvenanceRecord
from app.schemas.sandbox import (
    SandboxCapability,
    SandboxExecutionStatus,
    SandboxInvocationMandate,
    SandboxResult,
)
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
                execution_id=mandate.execution_id,
                task_id=mandate.task_id,
                worker_role=mandate.worker_role,
                capability=mandate.capability,
                status=SandboxExecutionStatus.FAILED,
                success=False,
                error="simulated sandbox failure",
                provenance={"status": "failed", "execution_id": mandate.execution_id},
            )
        if mandate.capability == SandboxCapability.ALLOC:
            import json
            from app.integrations.sandbox.s_alloc_core import execute_s_alloc

            sanitized_output = execute_s_alloc(mandate.payload)
        else:
            sanitized_output = {
                "objective": mandate.payload.get("objective", "unknown"),
                "result": f"{mandate.capability.value} completed for {mandate.task_id}",
            }
        return SandboxResult(
            execution_id=mandate.execution_id,
            task_id=mandate.task_id,
            worker_role=mandate.worker_role,
            capability=mandate.capability,
            status=SandboxExecutionStatus.COMPLETED,
            success=True,
            sanitized_output=sanitized_output,
            provenance={"status": "completed", "execution_id": mandate.execution_id},
        )


def create_mock_remote_sandbox(
    settings: Any = None,
    provenance_recorder: Any = None,
) -> SandboxClient:
    """Create a SandboxClient wired to an injected mock remote container simulating specialist execution."""
    import json
    from unittest.mock import MagicMock
    from app.core.settings import SandboxSettings
    from app.integrations.sandbox.s_alloc_core import execute_s_alloc
    from app.integrations.sandbox.micro_tools import (
        execute_s_attr,
        execute_s_copy,
        execute_s_parse,
        execute_s_val,
    )

    written_payload: dict[str, Any] = {}
    last_command = ""
    mock_remote = MagicMock()

    def mock_write(file: str = "", content: str = ""):
        nonlocal written_payload
        try:
            written_payload = json.loads(content)
        except Exception:
            written_payload = {}

    def mock_exec(command: str = ""):
        nonlocal last_command
        last_command = command
        return MagicMock(exit_code=0, stderr="")

    mock_remote.file.write_file.side_effect = mock_write
    mock_remote.shell.exec_command.side_effect = mock_exec

    def mock_read(file: str = ""):
        if "s-copy" in last_command:
            out = execute_s_copy(written_payload)
        elif "s-attr" in last_command:
            out = execute_s_attr(written_payload)
        elif "s-val" in last_command:
            out = execute_s_val(written_payload)
        elif "s-parse" in last_command:
            out = execute_s_parse(written_payload)
        else:
            out = execute_s_alloc(written_payload)
        return MagicMock(data=MagicMock(content=json.dumps(out)))

    mock_remote.file.read_file.side_effect = mock_read
    mock_remote.code.execute_code.return_value = MagicMock(stdout="diff applied successfully")
    mock_remote.browser.navigate.return_value = MagicMock(content="<html><body>Price: $49.99</body></html>")

    client = SandboxClient(
        settings=settings or SandboxSettings(endpoint="http://remote-sandbox:8080"),
        provenance_recorder=provenance_recorder,
    )
    client._sandbox = mock_remote
    return client


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
        namespace: str = "default",
        embedding: list[float] | None = None,
        model: str | None = None,
        metric: str | None = None,
        session: Any = None,
        **kwargs: Any,
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
        self,
        *,
        tenant_id: str,
        query: str | None = None,
        query_vector: list[float] | None = None,
        top_k: int = 10,
        namespace: str | None = None,
        search_type: str = "exact",
        metric: str = "cosine",
        min_score: float = 0.0,
        ef_search: int = 40,
        session: Any = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        matches = [doc for doc in self._documents if doc["tenant_id"] == tenant_id]
        return matches[:top_k]


class FakeProvenanceRepository(ProvenanceRepository):
    """An in-memory ``ProvenanceRepository`` that never touches a real database."""

    def __init__(self) -> None:
        super().__init__(session_factory=None)  # type: ignore[arg-type]
        self._chains: dict[str, list[ProvenanceRecord]] = {}

    @property
    def records(self) -> list[ProvenanceRecord]:
        """Convenience property returning all stored records across all tenants."""
        recs: list[ProvenanceRecord] = []
        for chain in self._chains.values():
            recs.extend(chain)
        return recs

    async def _latest(
        self, tenant_id: str, *, session: Any = None
    ) -> ProvenanceRecord | None:
        records = self._chains.get(tenant_id, [])
        return records[-1] if records else None

    async def append(
        self,
        *,
        tenant_id: str,
        entity_id: str,
        activity: str,
        agent: str,
        record_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        w3c_prov: dict[str, Any] | None = None,
        session: Any = None,
        **kwargs: Any,
    ) -> ProvenanceRecord:
        # Idempotency check: return existing record if record_id already in tenant chain
        if record_id is not None:
            for existing in self._chains.get(tenant_id, []):
                if existing.record_id == record_id:
                    return existing

        occurred_at = datetime.now(UTC)
        latest = await self._latest(tenant_id)
        prev_hash = latest.record_hash if latest else None
        meta_hash = _compute_metadata_hash(metadata, w3c_prov)
        record = ProvenanceRecord(
            record_id=record_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
            entity_id=entity_id,
            activity=activity,
            agent=agent,
            occurred_at=occurred_at,
            prev_record_hash=prev_hash,
            metadata_hash=meta_hash,
            record_hash=_compute_hash(
                prev_hash, entity_id, activity, agent, occurred_at, meta_hash
            ),
            metadata=metadata or {},
            w3c_prov=w3c_prov or {},
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
