"""Unit tests for Layer-4 database, migration, and tenant-security foundation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel
from sqlalchemy import MetaData, Table
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RepositoryError
from app.core.settings import DatabaseSettings
from app.persistence.database import Database
from app.persistence.repositories.base import BaseJsonRepository, standard_table


class SampleRecord(BaseModel):
    name: str
    value: int


@pytest.fixture
def mock_db_settings() -> DatabaseSettings:
    return DatabaseSettings(
        dsn="postgresql+asyncpg://app_runtime:secret@localhost:5432/enterprise_os",
        migration_dsn="postgresql+asyncpg://postgres:admin_secret@localhost:5432/enterprise_os",
        pool_size=5,
        max_overflow=2,
        pool_timeout=10,
        enforce_rls=True,
        require_non_privileged_role=True,
    )


@pytest.fixture
def database_instance(mock_db_settings: DatabaseSettings) -> Database:
    with patch("app.persistence.database.create_async_engine") as mock_create:
        mock_engine = MagicMock()
        mock_create.return_value = mock_engine
        db = Database(mock_db_settings)
        return db


def make_mock_session_factory(session: AsyncSession) -> MagicMock:
    factory = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    factory.return_value = ctx
    return factory


# 1. Connection/Pool and Session/Transaction Handling Tests


@pytest.mark.asyncio
async def test_session_tenant_rls_propagation(database_instance: Database) -> None:
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.is_active = True
    database_instance._session_factory = make_mock_session_factory(mock_session)

    async with database_instance.session(tenant_id="tenant-alpha") as session:
        assert session is mock_session
        mock_session.execute.assert_awaited()
        call_args = mock_session.execute.call_args[0]
        text_clause = call_args[0]
        params = call_args[1] if len(call_args) > 1 else mock_session.execute.call_args[1]
        assert "SET LOCAL app.current_tenant" in str(text_clause)
        assert params.get("tenant_id") == "tenant-alpha"
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_tenant_session_rejects_empty_tenant(database_instance: Database) -> None:
    with pytest.raises(ValueError, match="non-empty tenant_id is required"):
        async with database_instance.tenant_session(""):
            pass

    with pytest.raises(ValueError, match="non-empty tenant_id is required"):
        async with database_instance.tenant_session("   "):
            pass


@pytest.mark.asyncio
async def test_transaction_caller_session_participation(database_instance: Database) -> None:
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.in_transaction.return_value = True

    # When participating in existing transaction, it uses begin_nested (savepoint)
    async with database_instance.transaction(session=mock_session) as session:
        assert session is mock_session
        mock_session.begin_nested.assert_called_once()


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(database_instance: Database) -> None:
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.in_transaction.return_value = False
    mock_tx = AsyncMock()
    mock_session.begin.return_value = mock_tx
    mock_tx.__aenter__.return_value = mock_tx
    database_instance._session_factory = make_mock_session_factory(mock_session)

    with pytest.raises(RuntimeError, match="Simulated failure"):
        async with database_instance.transaction():
            raise RuntimeError("Simulated failure")

    mock_session.rollback.assert_awaited()


# 2. Database Capability and Healthcheck Tests


@pytest.mark.asyncio
async def test_healthcheck_success_no_credential_leak(database_instance: Database) -> None:
    mock_session = AsyncMock(spec=AsyncSession)
    database_instance._session_factory = make_mock_session_factory(mock_session)
    database_instance._engine = MagicMock()
    database_instance._engine.pool.size.return_value = 5
    database_instance._engine.pool.checkedin.return_value = 4
    database_instance._engine.pool.checkedout.return_value = 1
    database_instance._engine.pool.overflow.return_value = 0

    with patch.object(
        database_instance,
        "verify_extensions",
        AsyncMock(return_value={"vector": True, "timescaledb": True}),
    ):
        result = await database_instance.healthcheck()

    assert result["status"] == "healthy"
    assert "secret" not in str(result)
    assert "admin_secret" not in str(result)
    assert result["pool"]["size"] == 5
    assert result["extensions"]["vector"] is True


@pytest.mark.asyncio
async def test_verify_extensions_reports_missing(database_instance: Database) -> None:
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("vector",)]
    mock_conn.execute.return_value = mock_result
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    database_instance._engine.connect.return_value = ctx

    with pytest.raises(RuntimeError, match="Missing required database extensions"):
        await database_instance.verify_extensions(
            required=["vector", "timescaledb"], fail_on_missing=True
        )


# 3. Privilege Separation and Role Restrictions


@pytest.mark.asyncio
async def test_verify_runtime_role_enforcement(database_instance: Database) -> None:
    from app.core.exceptions import PolicyViolationError

    mock_conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    database_instance._engine.connect.return_value = ctx

    # Superuser role must fail
    mock_result_superuser = MagicMock()
    mock_result_superuser.fetchone.return_value = ("postgres", "on")
    mock_conn.execute.return_value = mock_result_superuser

    with pytest.raises(PolicyViolationError, match="Privileged database role 'postgres' detected"):
        await database_instance.verify_runtime_role()

    # BYPASSRLS role must fail
    mock_result_user = MagicMock()
    mock_result_user.fetchone.return_value = ("app_user", "off")
    mock_result_bypass = MagicMock()
    mock_result_bypass.fetchone.return_value = (True,)
    mock_conn.execute.side_effect = [mock_result_user, mock_result_bypass]

    with pytest.raises(PolicyViolationError, match="Privileged database role 'app_user' detected"):
        await database_instance.verify_runtime_role()

    # Valid non-privileged role passes
    mock_result_valid_user = MagicMock()
    mock_result_valid_user.fetchone.return_value = ("app_runtime", "off")
    mock_result_nobypass = MagicMock()
    mock_result_nobypass.fetchone.return_value = (False,)
    mock_conn.execute.side_effect = [mock_result_valid_user, mock_result_nobypass]

    role_info = await database_instance.verify_runtime_role()
    assert role_info["current_user"] == "app_runtime"
    assert role_info["is_superuser"] is False
    assert role_info["bypass_rls"] is False
    assert role_info["compliant"] is True


# 4. BaseJsonRepository Isolation & Transaction Participation Tests


@pytest.fixture
def repo_table() -> Table:
    meta = MetaData()
    return standard_table("test_records", meta)


@pytest.fixture
def base_repo(repo_table: Table) -> BaseJsonRepository[SampleRecord]:
    session_factory = MagicMock()
    return BaseJsonRepository[SampleRecord](
        session_factory=session_factory,
        table=repo_table,
        serialize=lambda m: m.model_dump(mode="json"),
        deserialize=lambda d: SampleRecord.model_validate(d),
    )


@pytest.mark.asyncio
async def test_repo_save_fails_on_missing_tenant(
    base_repo: BaseJsonRepository[SampleRecord],
) -> None:
    model = SampleRecord(name="test", value=42)
    with pytest.raises(RepositoryError, match="Tenant ID cannot be empty"):
        await base_repo.save("rec-1", "", model)

    with pytest.raises(RepositoryError, match="Tenant ID cannot be empty"):
        await base_repo.save("rec-1", "   ", model)


@pytest.mark.asyncio
async def test_repo_cross_tenant_write_rejection(
    base_repo: BaseJsonRepository[SampleRecord],
) -> None:
    model = SampleRecord(name="test", value=42)
    session = AsyncMock(spec=AsyncSession)

    # Existing record belongs to tenant-owner-A
    mock_row = MagicMock()
    mock_row.scalar_one_or_none.return_value = "tenant-owner-A"
    session.execute.return_value = mock_row

    # Attempting to save under tenant-attacker-B must fail closed
    with pytest.raises(RepositoryError, match="Cross-tenant access violation"):
        await base_repo.save("rec-1", "tenant-attacker-B", model, session=session)


@pytest.mark.asyncio
async def test_repo_participates_in_caller_session_without_autocommit(
    base_repo: BaseJsonRepository[SampleRecord],
) -> None:
    model = SampleRecord(name="test", value=100)
    caller_session = AsyncMock(spec=AsyncSession)

    # No existing record
    mock_row = MagicMock()
    mock_row.scalar_one_or_none.return_value = None
    caller_session.execute.return_value = mock_row

    await base_repo.save("rec-100", "tenant-1", model, session=caller_session)

    # Caller session executed queries but did not auto-commit
    caller_session.execute.assert_awaited()
    caller_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_repo_get_and_require_tenant_bounding(
    base_repo: BaseJsonRepository[SampleRecord],
) -> None:
    session = AsyncMock(spec=AsyncSession)
    mock_row = MagicMock()
    mock_row.scalar_one_or_none.return_value = {"name": "bounded", "value": 7}
    session.execute.return_value = mock_row

    res = await base_repo.get("rec-7", tenant_id="tenant-1", session=session)
    assert res is not None
    assert res.name == "bounded"

    # Missing record raises on require
    mock_row.scalar_one_or_none.return_value = None
    with pytest.raises(RepositoryError, match="No record found with id 'rec-7' for tenant 'tenant-1'"):
        await base_repo.require("rec-7", tenant_id="tenant-1", session=session)


# 5. Migration Engine Ordering Test


@pytest.mark.asyncio
async def test_apply_migrations_ordering_and_tracking(database_instance: Database) -> None:
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    mock_engine.begin.return_value = ctx
    database_instance._migration_engine = mock_engine

    # Simulate empty schema_migrations initially
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_conn.execute.return_value = mock_result

    applied = await database_instance.apply_migrations()

    # All 6 migrations applied in exact numerical order
    expected = [
        "0001_layer4_extensions.sql",
        "0002_layer4_core.sql",
        "0003_memory_artifact_provenance.sql",
        "0004_telemetry_hypertable.sql",
        "0005_tenant_rls_privileges.sql",
        "0006_layer4_indexes.sql",
    ]
    assert applied == expected
