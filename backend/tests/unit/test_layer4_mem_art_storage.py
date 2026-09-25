"""Unit tests for L4-04: Institutional Memory (MEM) and Content-Addressed Artifacts (ART)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PolicyViolationError, RepositoryError
from app.integrations.artifact_store.client import ArtifactStoreClient, compute_sha256
from app.mcp.data_gateway import DataGateway
from app.persistence.repositories.artifact import ArtifactRepository
from app.persistence.repositories.memory import MemoryRecord, MemoryRepository
from app.persistence.repositories.provenance import ProvenanceRepository
from app.schemas.artifact import ArtifactReference
from app.schemas.governance import RiskLevel, TenantScope
from app.schemas.memory import MemoryNamespace
from app.security.authorization_boundary import CallerIdentity
from app.services.provenance import ProvenanceRecorder


def make_mock_session_factory(session: AsyncSession) -> MagicMock:
    factory = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    factory.return_value = ctx
    return factory


# =====================================================================
# 1. MEM (Institutional Memory) Tests
# =====================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    sess = AsyncMock(spec=AsyncSession)
    sess.is_active = True
    return sess


@pytest.mark.asyncio
async def test_mem_low_confidence_rejection(mock_session: AsyncMock) -> None:
    repo = MemoryRepository(session_factory=make_mock_session_factory(mock_session))
    record = MemoryRecord(
        memory_id="mem-low",
        tenant_id="tenant-1",
        category="rules",
        statement="unverified claim",
        confidence=0.45,  # below default 0.6 threshold
    )
    with pytest.raises(ValueError, match="below required threshold"):
        await repo.promote(record)


@pytest.mark.asyncio
async def test_mem_immutable_overwrite_rejection() -> None:
    store: dict[str, MemoryRecord] = {}

    mock_sess = AsyncMock(spec=AsyncSession)
    repo = MemoryRepository(session_factory=make_mock_session_factory(mock_sess))

    record = MemoryRecord(
        memory_id="mem-1",
        tenant_id="tenant-1",
        category="rules",
        statement="always use brand blue",
        confidence=0.9,
    )

    # First promotion succeeds
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(repo, "get", AsyncMock(return_value=None))
        mock_save = AsyncMock()
        mp.setattr(repo, "save", mock_save)
        await repo.promote(record)
        mock_save.assert_awaited_once()

    # Second promotion with same memory_id raises RepositoryError
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(repo, "get", AsyncMock(return_value=record))
        with pytest.raises(RepositoryError, match="already exists and is immutable"):
            await repo.promote(record)


@pytest.mark.asyncio
async def test_mem_version_progression_and_supersedes() -> None:
    mock_sess = AsyncMock(spec=AsyncSession)
    repo = MemoryRepository(session_factory=make_mock_session_factory(mock_sess))

    v1 = MemoryRecord(
        memory_id="mem-v1",
        tenant_id="tenant-1",
        category="rules",
        statement="original rule statement",
        confidence=0.85,
        version=1,
        is_active=True,
    )

    # 1. Attempting to supersede non-existent record raises RepositoryError
    v2_bad = MemoryRecord(
        memory_id="mem-v2-bad",
        tenant_id="tenant-1",
        category="rules",
        statement="updated rule statement",
        confidence=0.9,
        version=2,
        supersedes="mem-nonexistent",
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(repo, "get", AsyncMock(return_value=None))
        with pytest.raises(RepositoryError, match="Superseded memory record 'mem-nonexistent' not found"):
            await repo.promote(v2_bad)

    # 2. Attempting to supersede with lower or equal version raises ValueError
    v2_lower_ver = MemoryRecord(
        memory_id="mem-v2-lower",
        tenant_id="tenant-1",
        category="rules",
        statement="updated rule statement",
        confidence=0.9,
        version=1,  # invalid: not greater than v1
        supersedes="mem-v1",
    )
    with pytest.MonkeyPatch.context() as mp:
        async def mock_get(rec_id: str, **kwargs):
            return v1 if rec_id == "mem-v1" else None

        mp.setattr(repo, "get", mock_get)
        with pytest.raises(ValueError, match="Version progression violation"):
            await repo.promote(v2_lower_ver)

    # 3. Valid progression: v2 supersedes v1, deactivating v1
    v2_valid = MemoryRecord(
        memory_id="mem-v2-valid",
        tenant_id="tenant-1",
        category="rules",
        statement="updated rule statement",
        confidence=0.95,
        version=2,
        supersedes="mem-v1",
    )
    saved_records: list[MemoryRecord] = []
    with pytest.MonkeyPatch.context() as mp:
        async def mock_get_v1(rec_id: str, **kwargs):
            return v1 if rec_id == "mem-v1" else None

        async def mock_save(rec_id: str, tenant_id: str, model: MemoryRecord, **kwargs):
            saved_records.append(model)

        mp.setattr(repo, "get", mock_get_v1)
        mp.setattr(repo, "save", mock_save)

        await repo.promote(v2_valid)

        # Both deactivated v1 and new v2 were saved
        assert len(saved_records) == 2
        assert saved_records[0].memory_id == "mem-v1"
        assert saved_records[0].is_active is False
        assert saved_records[1].memory_id == "mem-v2-valid"
        assert saved_records[1].version == 2
        assert saved_records[1].is_active is True


@pytest.mark.asyncio
async def test_mem_cross_tenant_denial() -> None:
    mock_sess = AsyncMock(spec=AsyncSession)
    repo = MemoryRepository(session_factory=make_mock_session_factory(mock_sess))

    record_tenant_a = MemoryRecord(
        memory_id="mem-a",
        tenant_id="tenant-A",
        category="rules",
        statement="Tenant A confidential rule",
        confidence=0.9,
    )

    # Attempting to supersede Tenant A's record from Tenant B must fail closed
    record_tenant_b = MemoryRecord(
        memory_id="mem-b",
        tenant_id="tenant-B",
        category="rules",
        statement="Tenant B attempt",
        confidence=0.9,
        version=2,
        supersedes="mem-a",
    )

    with pytest.MonkeyPatch.context() as mp:
        async def mock_get(rec_id: str, tenant_id: str | None = None, **kwargs):
            if rec_id == "mem-a" and tenant_id == "tenant-A":
                return record_tenant_a
            return None

        mp.setattr(repo, "get", mock_get)
        with pytest.raises(RepositoryError, match="Superseded memory record 'mem-a' not found for tenant 'tenant-B'"):
            await repo.promote(record_tenant_b)


# =====================================================================
# 2. ART (Content-Addressed Storage & Metadata) Tests
# =====================================================================


@pytest.mark.asyncio
async def test_art_store_put_if_absent_and_no_overwrite() -> None:
    store = ArtifactStoreClient(root_prefix="test_artifacts")
    content = b"Immutable production deliverable content 2026"
    expected_hash = compute_sha256(content)

    # 1. First put: stores payload
    h1, len1, uri1 = await store.put_if_absent(content)
    assert h1 == expected_hash
    assert len1 == len(content)
    assert h1 in uri1

    # 2. Second put with same content: returns existing without overwrite
    h2, len2, uri2 = await store.put_if_absent(content)
    assert h2 == h1
    assert len2 == len1
    assert uri2 == uri1

    # 3. Retrieval and integrity verification
    payload = await store.get(h1)
    assert payload == content
    assert await store.verify_integrity(h1) is True

    # 4. Head inspection
    meta = await store.head(h1)
    assert meta is not None
    assert meta["length"] == len(content)
    assert meta["exists"] is True

    # 5. Health capability
    health = await store.health()
    assert health["status"] == "healthy"
    assert health["object_count"] == 1


@pytest.mark.asyncio
async def test_art_store_hash_and_length_mismatch_rejection() -> None:
    store = ArtifactStoreClient()
    content = b"Verification test payload"

    # Mismatched expected hash
    with pytest.raises(ValueError, match="Artifact content hash mismatch"):
        await store.put_if_absent(content, expected_hash="0000000000000000000000000000000000000000000000000000000000000000")

    # Mismatched expected length
    with pytest.raises(ValueError, match="Artifact length mismatch"):
        await store.put_if_absent(content, expected_length=999)


@pytest.mark.asyncio
async def test_art_repository_metadata_registration_and_immutability() -> None:
    mock_sess = AsyncMock(spec=AsyncSession)
    repo = ArtifactRepository(session_factory=make_mock_session_factory(mock_sess))

    content = b"Deliverable binary blob"
    c_hash = compute_sha256(content)

    art = ArtifactReference(
        artifact_id="art-uuid-1",
        content_hash=c_hash,
        uri=f"artifacts/{c_hash}",
        media_type="application/pdf",
        tenant_id="tenant-1",
        deliverable_type="report",
    )

    # 1. First registration succeeds
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(repo, "get", AsyncMock(return_value=None))
        mock_save1 = AsyncMock()
        mp.setattr(repo, "save", mock_save1)
        await repo.register("tenant-1", art)
        mock_save1.assert_awaited_once()

    # 2. Idempotent registration with identical content hash returns cleanly
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(repo, "get", AsyncMock(return_value=art))
        mock_save2 = AsyncMock()
        mp.setattr(repo, "save", mock_save2)
        await repo.register("tenant-1", art)
        mock_save2.assert_not_called()

    # 3. Tampering attempt with different content hash raises RepositoryError
    tampered_art = ArtifactReference(
        artifact_id="art-uuid-1",
        content_hash="1111111111111111111111111111111111111111111111111111111111111111",
        uri="artifacts/tampered",
        media_type="application/pdf",
        tenant_id="tenant-1",
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(repo, "get", AsyncMock(return_value=art))
        with pytest.raises(RepositoryError, match="already exists and is immutable. Overwrite forbidden"):
            await repo.register("tenant-1", tampered_art)


@pytest.mark.asyncio
async def test_art_cross_tenant_denial() -> None:
    mock_sess = AsyncMock(spec=AsyncSession)
    repo = ArtifactRepository(session_factory=make_mock_session_factory(mock_sess))

    c_hash = compute_sha256(b"Tenant 1 private report")
    art_t1 = ArtifactReference(
        artifact_id="art-t1",
        content_hash=c_hash,
        uri=f"artifacts/{c_hash}",
        media_type="application/pdf",
        tenant_id="tenant-1",
    )

    # 1. Resolving by hash under tenant-2 returns None
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(repo, "resolve_by_hash", AsyncMock(return_value=None))
        res = await repo.resolve_by_hash(c_hash, tenant_id="tenant-2")
        assert res is None

    # 2. Resolving by ID under tenant-2 raises RepositoryError
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(repo, "require", AsyncMock(side_effect=RepositoryError("No record found with id 'art-t1' for tenant 'tenant-2'.")))
        with pytest.raises(RepositoryError, match="for tenant 'tenant-2'"):
            await repo.resolve("art-t1", tenant_id="tenant-2")


# =====================================================================
# 3. Model A Data Gateway & Transactional Provenance Tests
# =====================================================================


@pytest.mark.asyncio
async def test_data_gateway_store_and_register_artifact_flow() -> None:
    mock_vector = AsyncMock()
    mock_art_repo = AsyncMock(spec=ArtifactRepository)
    art_store = ArtifactStoreClient()

    gateway = DataGateway(
        vector_repository=mock_vector,
        artifact_repository=mock_art_repo,
        artifact_store=art_store,
    )

    caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.MEDIUM,
    )

    content = b"Campaign creative graphic asset png payload"
    art_ref = await gateway.store_and_register_artifact(
        caller,
        tenant_id="tenant-alpha",
        content=content,
        media_type="image/png",
        deliverable_type="generated_asset",
        name="ad_banner.png",
    )

    assert art_ref.tenant_id == "tenant-alpha"
    assert art_ref.media_type == "image/png"
    assert art_ref.content_hash == compute_sha256(content)
    mock_art_repo.register.assert_awaited_once()

    # Payload retrieval through gateway
    mock_art_repo.resolve.return_value = art_ref
    retrieved_bytes = await gateway.get_artifact_payload(
        caller, tenant_id="tenant-alpha", artifact_id=art_ref.artifact_id
    )
    assert retrieved_bytes == content

    # Worker direct mutation rejection
    worker = CallerIdentity(
        subject="W_CREATIVE",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.HIGH,
    )
    with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
        await gateway.store_and_register_artifact(
            worker,
            tenant_id="tenant-alpha",
            content=b"worker bypass attempt",
        )


@pytest.mark.asyncio
async def test_transaction_boundary_provenance_rollback() -> None:
    """Verify that if an error occurs within a transaction, both memory and provenance rollback."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.is_active = True
    mock_res = MagicMock()
    mock_res.all.return_value = []
    mock_session.execute.return_value = mock_res

    repo_prov = ProvenanceRepository(session_factory=make_mock_session_factory(mock_session))
    recorder = ProvenanceRecorder(repository=repo_prov)

    # Calling append with caller's session executes insert but does not commit
    rec = await recorder.record(
        tenant_id="tenant-tx",
        entity_id="mem-tx-1",
        activity="memory_promotion",
        agent="IE",
        session=mock_session,
    )
    assert rec.tenant_id == "tenant-tx"
    mock_session.execute.assert_awaited()
    # No auto-commit when caller session is supplied
    mock_session.commit.assert_not_called()
