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

    def __init__(self, session_factory: Any = None) -> None:
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


@pytest.mark.asyncio
async def test_t01_raw_before_parse_cryptographic_verification() -> None:
    """T01: Authenticated deliveries are verified against raw request bytes before parsing; key rotation supported."""
    import hashlib
    import hmac
    import time
    from datetime import datetime, timezone
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.schemas.telemetry import OmnichannelTelemetryReadiness, TelemetrySurface, TelemetrySourceType, TelemetryEventType
    from app.services.telemetry_engine import OmnichannelTelemetryEngine
    from app.security.cryptographic_validator import ProviderHmacValidator, verify_raw_webhook_signature

    now_iso = datetime.now(timezone.utc).isoformat()
    raw_payload = f'{{"tenant_id": "tenant-sec", "channel": "meta", "event_type": "ad_spend", "occurred_at": "{now_iso}", "metrics": {{"spend": 100.0}}}}'.encode()
    secret = "primary_secret_123"
    rotated_secret = "secondary_secret_456"

    # 1. Meta provider verification with prefix 'sha256='
    computed_sig = hmac.new(secret.encode(), raw_payload, hashlib.sha256).hexdigest()
    assert ProviderHmacValidator.verify_meta(raw_payload, f"sha256={computed_sig}", secret) is True
    assert ProviderHmacValidator.verify_meta(raw_payload, "sha256=invalid_hash", secret) is False

    # 2. Key rotation verification
    computed_rotated = hmac.new(rotated_secret.encode(), raw_payload, hashlib.sha256).hexdigest()
    assert (
        ProviderHmacValidator.verify_meta(
            raw_payload, f"sha256={computed_rotated}", [secret, rotated_secret]
        )
        is True
    )

    # 3. TikTok signature verification with timestamp
    now_ts = str(int(time.time()))
    tiktok_msg = now_ts.encode() + raw_payload
    tt_sig = hmac.new(secret.encode(), tiktok_msg, hashlib.sha256).hexdigest()
    assert (
        ProviderHmacValidator.verify_tiktok(
            raw_payload, tt_sig, now_ts, secret, tolerance_seconds=300
        )
        is True
    )
    # Expired timestamp fails
    old_ts = str(int(time.time()) - 1000)
    assert (
        ProviderHmacValidator.verify_tiktok(
            raw_payload, tt_sig, old_ts, secret, tolerance_seconds=300
        )
        is False
    )

    # 4. Route-level verification: raw invalid bytes or forged signature fails with 401 before schema parsing
    engine = OmnichannelTelemetryEngine(webhook_signing_secret=secret)
    surface = TelemetrySurface(
        channel="meta",
        source_type=TelemetrySourceType.WEBHOOK,
        endpoint="/api/v1/telemetry/webhooks/ads/meta",
        tenant_id="tenant-sec",
        event_classes=[TelemetryEventType.AD_SPEND],
        is_active=True,
    )
    engine.register_surface(surface)
    engine.register_readiness(
        OmnichannelTelemetryReadiness(
            readiness_id="r-1",
            tenant_id="tenant-sec",
            is_ready=True,
            dependencies={},
            active_surfaces=[surface],
            probes=[],
            blocked_reasons=[],
        )
    )
    orig_engine = getattr(app.state, "telemetry_engine", None)
    app.state.telemetry_engine = engine
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Invalid signature on raw body -> HTTP 401
            res = await client.post(
                "/telemetry/webhooks/ads/meta",
                content=raw_payload,
                headers={"X-Hub-Signature-256": "sha256=bad_sig", "Content-Type": "application/json"},
            )
            assert res.status_code == 401

            # Valid signature -> HTTP 202 with opaque receipt
            res_ok = await client.post(
                "/telemetry/webhooks/ads/meta",
                content=raw_payload,
                headers={"X-Hub-Signature-256": f"sha256={computed_sig}", "Content-Type": "application/json"},
            )
            assert res_ok.status_code == 202
            body = res_ok.json()
            assert body["status"] == "accepted"
            assert body["tenant_id"] == "tenant-sec"
            assert "receipt_id" in body
    finally:
        app.state.telemetry_engine = orig_engine


@pytest.mark.asyncio
async def test_t02_ingress_tenant_spoofing_and_browser_untrusted() -> None:
    """T02: Spoofed tenant/account rejected; browser traffic marked browser_untrusted and never authoritative orders."""
    from datetime import datetime, timezone
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.schemas.telemetry import OmnichannelTelemetryReadiness, TelemetrySurface, TelemetrySourceType, TelemetryEventType
    from app.services.telemetry_engine import OmnichannelTelemetryEngine

    now_iso = datetime.now(timezone.utc).isoformat()
    engine = OmnichannelTelemetryEngine(webhook_signing_secret=None)
    surface = TelemetrySurface(
        channel="website",
        source_type=TelemetrySourceType.PIXEL,
        endpoint="/telemetry/pixel",
        tenant_id="tenant-real",
        event_classes=[TelemetryEventType.TRAFFIC, TelemetryEventType.CONVERSION],
        is_active=True,
    )
    engine.register_surface(surface)
    engine.register_readiness(
        OmnichannelTelemetryReadiness(
            readiness_id="r-2",
            tenant_id="tenant-real",
            is_ready=True,
            dependencies={},
            active_surfaces=[surface],
            probes=[],
            blocked_reasons=[],
        )
    )
    orig_engine = getattr(app.state, "telemetry_engine", None)
    app.state.telemetry_engine = engine

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Spoofed tenant ID on active surface -> HTTP 403
            spoofed_payload = {
                "tenant_id": "tenant-attacker",
                "channel": "website",
                "event_type": "traffic",
                "occurred_at": now_iso,
                "metrics": {"pageviews": 1.0},
            }
            res_spoof = await client.post("/telemetry/pixel", json=spoofed_payload)
            assert res_spoof.status_code == 403

            # 2. Browser purchase marked browser_untrusted and never authoritative order
            purchase_payload = {
                "tenant_id": "tenant-real",
                "channel": "website",
                "event_type": "conversion",
                "occurred_at": now_iso,
                "metrics": {"revenue": 250.0},
                "payload": {"order_id": "ord-123", "is_authoritative_order": True},
            }
            res_purchase = await client.post("/telemetry/pixel", json=purchase_payload)
            assert res_purchase.status_code == 202
            receipt = res_purchase.json()
            assert receipt["status"] == "accepted"
            # Verify minimized payload stripped authoritative order flag
            min_p = receipt.get("minimized_payload", {}).get("properties", {})
            assert min_p.get("is_authoritative_order") is False
    finally:
        app.state.telemetry_engine = orig_engine


@pytest.mark.asyncio
async def test_t13_cms_release_stamping_and_site_availability_isolation() -> None:
    """T13: Deployed CMS release is stamped on telemetry, and admission failure never takes down production site."""
    from datetime import datetime, timezone
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.integrations.cms.client import CmsClient
    from app.core.exceptions import RepositoryError
    from app.schemas.telemetry import OmnichannelTelemetryReadiness, TelemetrySurface, TelemetrySourceType, TelemetryEventType
    from app.services.telemetry_engine import OmnichannelTelemetryEngine

    # 1. CMS deploy stamps release_id
    cms = CmsClient()
    deploy_res = await cms.deploy_payload(
        {"items": [{"content_type": "pages", "id": "p-1", "title": "Home"}]},
        tenant_id="tenant-rel",
    )
    assert deploy_res is not None
    assert deploy_res["status"] == "published"
    assert "release_id" in deploy_res
    release_id = deploy_res["release_id"]
    current_rel = cms.get_current_release("tenant-rel")
    assert current_rel is not None
    assert current_rel["release_id"] == release_id

    # 2. Site availability isolation: telemetry failure returns HTTP 503 without crash
    now_iso = datetime.now(timezone.utc).isoformat()
    engine = OmnichannelTelemetryEngine(webhook_signing_secret=None)
    surface = TelemetrySurface(
        channel="website",
        source_type=TelemetrySourceType.PIXEL,
        endpoint="/telemetry/pixel",
        tenant_id="tenant-rel",
        event_classes=[TelemetryEventType.TRAFFIC, TelemetryEventType.CONVERSION],
        is_active=True,
    )
    engine.register_surface(surface)
    engine.register_readiness(
        OmnichannelTelemetryReadiness(
            readiness_id="r-3",
            tenant_id="tenant-rel",
            is_ready=True,
            dependencies={},
            active_surfaces=[surface],
            probes=[],
            blocked_reasons=[],
        )
    )
    orig_engine = getattr(app.state, "telemetry_engine", None)
    orig_repo = getattr(app.state, "telemetry_repository", None)
    app.state.telemetry_engine = engine

    class BrokenRepository(FakeTelemetryRepository):
        async def admit(self, record: Any, *, session: Any = None) -> Any:
            raise RepositoryError("Underlying TimescaleDB unreachable")

    app.state.telemetry_repository = BrokenRepository()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "tenant_id": "tenant-rel",
                "channel": "website",
                "event_type": "traffic",
                "occurred_at": now_iso,
                "metrics": {"pageviews": 1.0},
            }
            res = await client.post("/telemetry/pixel", json=payload)
            # Safe 503 error returned, preventing cascade
            assert res.status_code == 503
            assert "Telemetry admission failure" in res.json()["detail"]
    finally:
        app.state.telemetry_engine = orig_engine
        app.state.telemetry_repository = orig_repo


@pytest.mark.asyncio
async def test_t12_missing_stale_suppressed_metrics_and_worker_direct_retrieval_denied() -> None:
    from datetime import datetime, timedelta, timezone
    from app.agents.strategy_engine.strategy import StrategyAgent
    from app.orchestration.brand_persona import BrandPersonaResolver
    from app.orchestration.context_assembly import ContextAssembler
    from app.orchestration.intelligence_engine import IntelligenceEngine
    from app.orchestration.rag_query_dispatch import RagQueryDispatcher
    from app.schemas.agent_contracts import TaskGrant
    from app.schemas.governance import WorkerRole
    from app.schemas.strategy import PerformanceContextReference
    from app.services.rag.controller import RagController
    from app.services.rag.freshness import FreshnessPolicy
    from app.services.rag.hybrid_retriever import HybridRetriever
    from app.services.rag.schema_validator import SchemaValidator

    # 1. Direct worker retrieval without valid IE token is strictly denied by RAG dispatcher
    rag_controller = RagController(
        retriever=HybridRetriever(FakeVectorRepository()),
        schema_validator=SchemaValidator(),
        freshness_policy=FreshnessPolicy(),
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    with pytest.raises(AuthorizationError, match="without a valid Intelligence Engine token"):
        await rag_dispatcher.dispatch(
            None,  # type: ignore[arg-type] # Direct worker caller lacks IE token
            tenant_id="acme",
            query="campaign metrics",
        )

    # 2. IE builds performance context preserving unavailable, stale, and suppressed metrics
    assembler = ContextAssembler(rag_dispatcher, BrandPersonaResolver())
    engine = IntelligenceEngine(
        policy_evaluator=MagicMock(),
        dag_scheduler=MagicMock(),
        task_state_machine=MagicMock(),
        context_assembler=assembler,
        evidence_synthesizer=MagicMock(),
        hitl_preview_generator=MagicMock(),
        hitl_coordinator=MagicMock(),
        mcp_host=MagicMock(),
        provenance_recorder=MagicMock(),
        workers={},
    )

    perf_ctx_dict = await engine.build_performance_context(
        tenant_id="acme",
        brand_id="brand-1",
        channels=["meta", "google", "tiktok"],
        requested_metrics=["roas", "cpa", "spend"],
        raw_performance_data={
            "meta": {"status": "valid", "value": 3.4},
            "google": {"status": "suppressed", "reason": "privacy_threshold"},
            "tiktok": {"status": "stale", "value": 1500.0, "staleness_seconds": 90000},
        },
    )
    perf_ctx = PerformanceContextReference.model_validate(perf_ctx_dict)

    # Verify missing/suppressed metrics are NOT zeroed or fabricated
    assert perf_ctx.metrics["meta"]["value"] == 3.4
    assert perf_ctx.metrics["meta"]["status"] == "valid"
    assert perf_ctx.metrics["google"]["value"] is None
    assert perf_ctx.metrics["google"]["status"] == "suppressed"
    assert perf_ctx.quality_flags["has_stale_data"] is True
    assert perf_ctx.quality_flags["has_suppression"] is True
    assert perf_ctx.is_valid is False

    # 3. Strategy agent verifies and gates on performance context quality and tenant boundaries
    grant = TaskGrant(
        task_id="task-strat-12",
        directive_id="dir-12",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme", allowed_channels=["meta", "google"]),
        brand_id="brand-1",
        allowed_capabilities=[],
        risk_ceiling=RiskLevel.LOW,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    strategy_agent = StrategyAgent()
    base_context = {
        "budget_ceiling": 5000.0,
        "channels": ["meta", "google"],
        "approved_claims": [{"claim_id": "c1", "text": "Best in class", "status": "approved"}],
        "objections": [{"objection_id": "o1", "theme": "Price"}],
        "competitor_signals": {"competitor": "CompetitorA", "benchmark_price": "29.99"},
    }

    # Blocked if performance context contains stale or suppressed data when required
    with pytest.raises(PolicyViolationError, match="Ungrounded budget allocation blocked"):
        strategy_agent._verify_and_normalize_dependencies(
            grant,
            {**base_context, "performance_context": perf_ctx, "require_performance_context": True},
        )

    # Blocked on tenant mismatch
    off_tenant_ctx = perf_ctx.model_copy(update={"tenant_id": "evil-corp"})
    with pytest.raises(ValueError, match="Tenant isolation breach in performance context"):
        strategy_agent._verify_and_normalize_dependencies(
            grant,
            {**base_context, "performance_context": off_tenant_ctx},
        )

    # Clean fresh performance context passes validation
    clean_dict = await engine.build_performance_context(
        tenant_id="acme",
        brand_id="brand-1",
        channels=["meta", "google"],
        requested_metrics=["roas", "spend"],
        raw_performance_data={
            "meta": {"status": "valid", "value": 3.4},
            "google": {"status": "valid", "value": 1500.0},
        },
    )
    clean_perf_ctx = PerformanceContextReference.model_validate(clean_dict)
    assert clean_perf_ctx.quality_flags["has_stale_data"] is False
    assert clean_perf_ctx.quality_flags["has_suppression"] is False
    assert clean_perf_ctx.quality_flags["is_complete"] is True
    assert clean_perf_ctx.is_valid is True

    deps = strategy_agent._verify_and_normalize_dependencies(
        grant,
        {**base_context, "performance_context": clean_perf_ctx, "require_performance_context": True},
    )
    assert deps[0] == 5000.0

    deps = strategy_agent._verify_and_normalize_dependencies(
        grant,
        {**base_context, "performance_context": clean_perf_ctx, "require_performance_context": True},
    )
    assert deps[0] == 5000.0



