"""Integration security verification tests for Layer-8 boundary hardening (T02, T03, T10, T11)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    AuthorizationError,
    PolicyViolationError,
    RepositoryError,
)
from app.core.settings import DatabaseSettings
from app.mcp.data_gateway import DataGateway
from app.persistence.database import Database
from app.persistence.repositories.telemetry import TelemetryRepository
from app.schemas.governance import RiskLevel, TenantScope
from app.schemas.telemetry import (
    RecordKind,
    TelemetryEnvelope,
    TrustClass,
)
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity
from app.services.provenance import ProvenanceRecorder
from app.services.telemetry import TelemetryService
from tests.conftest import FakeProvenanceRepository, FakeVectorRepository


class FakeTelemetryRepository(TelemetryRepository):
    """In-memory telemetry repository for boundary testing."""

    def __init__(self) -> None:
        self.receipts: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
        self.work_items: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []

    async def admit(
        self,
        record: dict[str, Any] | TelemetryEnvelope,
        *,
        session: Any = None,
    ) -> Any:
        from app.schemas.telemetry import TelemetryReceipt

        rec_dict = record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)

        tenant_id = rec_dict.get("tenant_id")
        if not tenant_id or not str(tenant_id).strip():
            raise RepositoryError("Tenant ID cannot be empty.")

        key = (
            tenant_id,
            rec_dict.get("source_id", "src"),
            rec_dict.get("source_account_id", "acc"),
            rec_dict.get("logical_event_id", "evt"),
            rec_dict.get("source_revision", "1"),
        )
        content_hash = rec_dict.get("content_hash", "hash_default")

        if key in self.receipts:
            prev = self.receipts[key]
            if prev["content_hash"] == content_hash:
                return TelemetryReceipt(
                    receipt_id=prev["receipt_id"],
                    tenant_id=tenant_id,
                    source_id=key[1],
                    source_account_id=key[2],
                    logical_event_id=key[3],
                    source_revision=key[4],
                    content_hash=content_hash,
                    status="duplicate",
                )
            return TelemetryReceipt(
                receipt_id=prev["receipt_id"],
                tenant_id=tenant_id,
                source_id=key[1],
                source_account_id=key[2],
                logical_event_id=key[3],
                source_revision=key[4],
                content_hash=content_hash,
                status="quarantined",
            )

        receipt_id = f"rcpt_{len(self.receipts) + 1}"
        stored = {
            "receipt_id": receipt_id,
            "tenant_id": tenant_id,
            "source_id": key[1],
            "source_account_id": key[2],
            "logical_event_id": key[3],
            "source_revision": key[4],
            "content_hash": content_hash,
            "minimized_payload": rec_dict.get("payload", {}),
            "status": "accepted",
        }
        self.receipts[key] = stored
        return TelemetryReceipt(
            receipt_id=receipt_id,
            tenant_id=tenant_id,
            source_id=key[1],
            source_account_id=key[2],
            logical_event_id=key[3],
            source_revision=key[4],
            content_hash=content_hash,
            status="accepted",
        )


@pytest.fixture
def auth_boundary() -> AuthorizationBoundary:
    return AuthorizationBoundary()


@pytest.fixture
def mock_gateway(auth_boundary: AuthorizationBoundary) -> DataGateway:
    repo = FakeTelemetryRepository()
    vector_repo = FakeVectorRepository()
    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(prov_repo)
    return DataGateway(
        vector_repository=vector_repo,
        authorization_boundary=auth_boundary,
        telemetry_repository=repo,
        provenance_recorder=recorder,
    )


# ==============================================================================
# T02: Tenant/Account Spoofing, Origin Trust & Surface Isolation
# ==============================================================================


@pytest.mark.asyncio
async def test_t02_cross_tenant_spoofing_denied(mock_gateway: DataGateway) -> None:
    """Caller with tenant-A authority cannot admit telemetry for tenant-B."""
    caller = CallerIdentity(
        subject="telemetry_collector",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.LOW,
        allowed_capabilities=frozenset({"telemetry.ingest"}),
    )

    expected_msg = "Caller 'telemetry_collector' has no delegated authority"
    with pytest.raises(AuthorizationError, match=expected_msg):
        await mock_gateway.admit(
            caller,
            tenant_id="tenant-beta",
            record={
                "tenant_id": "tenant-beta",
                "source_id": "src-1",
                "source_account_id": "acc-1",
                "logical_event_id": "evt-1",
                "payload": {"data": "test"},
            },
        )


@pytest.mark.asyncio
async def test_t02_browser_untrusted_cannot_claim_server_verification() -> None:
    """Browser untrusted telemetry preserves trust_class without masquerading."""
    envelope = TelemetryEnvelope(
        record_kind=RecordKind.EVENT,
        tenant_id="acme",
        brand_id="brand-1",
        source_id="web_browser",
        source_account_id="client_session",
        trust_class=TrustClass.BROWSER_UNTRUSTED,
        dimensions={"source": "browser"},
    )
    assert envelope.trust_class == TrustClass.BROWSER_UNTRUSTED
    assert envelope.trust_class != TrustClass.SERVER_VERIFIED


# ==============================================================================
# T03: Model-A Database Authority & Sandbox Isolation
# ==============================================================================


@pytest.mark.asyncio
async def test_t03_workers_denied_direct_gateway_telemetry_access(
    mock_gateway: DataGateway,
) -> None:
    """Model A: Worker agents (W_STRAT, W_LEARN, W_DEV) cannot access persistence directly."""
    for worker_role in ("W_STRAT", "W_LEARN", "W_CREATIVE", "worker_subagent"):
        worker_caller = CallerIdentity(
            subject=worker_role,
            tenant_scope=TenantScope(tenant_id="acme"),
            risk_ceiling=RiskLevel.LOW,
        )
        msg = "Direct worker enterprise-store access forbidden"
        with pytest.raises(PolicyViolationError, match=msg):
            await mock_gateway.admit(
                worker_caller,
                tenant_id="acme",
                record={"tenant_id": "acme", "payload": {}},
            )

        with pytest.raises(PolicyViolationError, match=msg):
            await mock_gateway.list_telemetry(worker_caller, tenant_id="acme")


@pytest.mark.asyncio
async def test_t03_sandbox_caller_denied_persistence(auth_boundary: AuthorizationBoundary) -> None:
    """Sandbox-originating callers are strictly blocked from database/persistence access."""
    sandbox_caller = CallerIdentity(
        subject="sandbox_runner",
        tenant_scope=TenantScope(tenant_id="acme"),
        risk_ceiling=RiskLevel.LOW,
    )
    msg = "Sandbox-originating caller 'sandbox_runner' is strictly forbidden"
    with pytest.raises(AuthorizationError, match=msg):
        auth_boundary.authorize_sandbox_action(
            sandbox_caller,
            target_resource="persistence_telemetry",
            is_sandbox_origin=True,
        )


# ==============================================================================
# T10: Runtime Role, NOBYPASSRLS & RLS Scope Enforcement
# ==============================================================================


@pytest.mark.asyncio
async def test_t10_privileged_superuser_and_bypassrls_rejected() -> None:
    """Database runtime role verification rejects superuser and BYPASSRLS roles."""
    db_settings = DatabaseSettings(
        dsn="postgresql+asyncpg://app_runtime:secret@localhost:5432/enterprise_os",
        require_non_privileged_role=True,
    )
    with patch("app.persistence.database.create_async_engine") as mock_create:
        mock_engine = MagicMock()
        mock_create.return_value = mock_engine
        db = Database(db_settings)

        mock_conn = AsyncMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        ctx.__aexit__ = AsyncMock(return_value=None)
        mock_engine.connect.return_value = ctx

        # Superuser check
        mock_result_superuser = MagicMock()
        mock_result_superuser.fetchone.return_value = ("postgres", "on")
        mock_conn.execute.return_value = mock_result_superuser

        err_super = "Privileged database role 'postgres' detected"
        with pytest.raises(PolicyViolationError, match=err_super):
            await db.verify_runtime_role()

        # BYPASSRLS check
        mock_result_user = MagicMock()
        mock_result_user.fetchone.return_value = ("app_user", "off")
        mock_result_bypass = MagicMock()
        mock_result_bypass.fetchone.return_value = (True,)
        mock_conn.execute.side_effect = [mock_result_user, mock_result_bypass]

        err_bypass = "Privileged database role 'app_user' detected"
        with pytest.raises(PolicyViolationError, match=err_bypass):
            await db.verify_runtime_role()

        # Valid non-privileged role
        mock_result_valid_user = MagicMock()
        mock_result_valid_user.fetchone.return_value = ("enterprise_runtime", "off")
        mock_result_nobypass = MagicMock()
        mock_result_nobypass.fetchone.return_value = (False,)
        mock_conn.execute.side_effect = [mock_result_valid_user, mock_result_nobypass]

        role_info = await db.verify_runtime_role()
        assert role_info["compliant"] is True
        assert role_info["is_superuser"] is False
        assert role_info["bypass_rls"] is False


@pytest.mark.asyncio
async def test_t10_empty_tenant_context_fails_closed() -> None:
    """Database tenant session fails closed if tenant_id is empty or whitespace."""
    db = Database(DatabaseSettings())
    with pytest.raises(ValueError, match="non-empty tenant_id is required"):
        async with db.tenant_session(""):
            pass


# ==============================================================================
# T11: Zero Raw Credentials & PII in Provenance and Minimized Envelopes
# ==============================================================================


@pytest.mark.asyncio
async def test_t11_secret_scrubbing_in_telemetry_and_provenance(mock_gateway: DataGateway) -> None:
    """Credentials, tokens, authorization headers, and payment cards are redacted before storage."""
    repo: FakeTelemetryRepository = mock_gateway._telemetry_repository  # type: ignore[assignment]
    service = TelemetryService(repository=repo, data_gateway=mock_gateway)

    dirty_payload = {
        "access_token": "ya29.a0AfH6SMD_secret_token_12345",
        "client_secret": "top_secret_key_abcdefg",
        "authorization": "Bearer secret_bearer_token",
        "credit_card": "4111 1111 1111 1111",
        "event_name": "checkout_completed",
        "amount": "99.99",
    }

    receipt = await service.admit(
        {
            "tenant_id": "acme",
            "source_id": "web_store",
            "source_account_id": "acc_01",
            "logical_event_id": "order_789",
            "payload": dirty_payload,
        }
    )

    assert receipt.status == "accepted"
    # Verify in-memory repository payload
    key = ("acme", "web_store", "acc_01", "order_789", "1")
    stored_doc = repo.receipts[key]["minimized_payload"]

    assert stored_doc["access_token"] == "[REDACTED]"
    assert stored_doc["client_secret"] == "[REDACTED]"
    assert stored_doc["authorization"] == "[REDACTED]"
    assert stored_doc["credit_card"] in ("[REDACTED]", "[REDACTED_PAYMENT_CARD]")
    assert stored_doc["event_name"] == "checkout_completed"

    # Verify provenance audit records contain zero raw secrets
    prov_repo: FakeProvenanceRepository = (
        mock_gateway._provenance_recorder._repository  # type: ignore[assignment]
    )
    audit_chain = await prov_repo.chain("acme")
    assert len(audit_chain) > 0
    for record in audit_chain:
        doc_str = str(record.model_dump(mode="json"))
        assert "ya29.a0AfH6SMD_secret_token_12345" not in doc_str
        assert "top_secret_key_abcdefg" not in doc_str
        assert "4111 1111 1111 1111" not in doc_str
