"""Comprehensive unit verification suite for Task-30 (T30): Ingest Live Operational Telemetry into CDB.

Validates:
- Authoritative T29 readiness requirement
- Live traffic, checkout, transaction, conversion, error, ad, and social telemetry ingestion
- Ingress signature authentication & active surface routing allowlists
- Timestamp freshness window (reject stale and future timestamps)
- Idempotent deduplication preventing duplicate CDB rows on webhook retries
- Financial / PII sensitive data scrubbing before persistence and provenance
- Explicit database failure handling (no false success)
- Batch ingestion with item-level partial failure diagnostics
- CTS state and immutable audit provenance tracking
- Zero T31 attribution/learning execution during ingestion
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
import pytest

from app.core.exceptions import (
    AuthorizationError,
    ConfigurationError,
    PolicyViolationError,
    RepositoryError,
    SignatureVerificationError,
)
from app.mcp.data_gateway import DataGateway
from app.persistence.repositories.telemetry import TelemetryRepository
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.schemas.telemetry import (
    BatchTelemetryIngestRequest,
    OmnichannelTelemetryReadiness,
    TelemetryEvent,
    TelemetryEventType,
    TelemetryHandshakeProbe,
    TelemetrySourceType,
    TelemetrySurface,
    WebhookIngestEnvelope,
)
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from app.services.telemetry import TelemetryNormalizer
from app.services.telemetry_engine import OmnichannelTelemetryEngine
from tests.conftest import FakeProvenanceRepository


class _InMemoryTelemetryRepository(TelemetryRepository):
    """An in-memory stand-in for the CDB JSONB-backed telemetry repository."""

    def __init__(self, should_fail: bool = False) -> None:
        self._store: dict[str, TelemetryEvent] = {}
        self.should_fail = should_fail

    async def record(self, event: TelemetryEvent) -> None:
        if self.should_fail:
            raise RepositoryError("Simulated database connection failure during write.")
        self._store[event.event_id] = event

    async def get(self, record_id: str) -> TelemetryEvent | None:
        return self._store.get(record_id)

    async def get_by_idempotency_key(self, tenant_id: str, idempotency_key: str) -> TelemetryEvent | None:
        for event in self._store.values():
            if event.tenant_id == tenant_id and event.idempotency_key == idempotency_key:
                return event
        return None

    async def list_by_tenant(self, tenant_id: str) -> list[TelemetryEvent]:
        return [e for e in self._store.values() if e.tenant_id == tenant_id]

    async def list_by_type(self, tenant_id: str, event_type: str) -> list[TelemetryEvent]:
        return [
            e
            for e in self._store.values()
            if e.tenant_id == tenant_id and e.event_type.value == event_type
        ]


class _FakeTaskStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task {task_id} not found")
        return self.states[task_id]


def _setup_t30_environment(
    tenant_id: str = "tenant-alpha",
    signing_secret: str | None = "test_signing_secret_xyz",
    db_should_fail: bool = False,
    t29_ready: bool = True,
) -> tuple[
    OmnichannelTelemetryEngine,
    _InMemoryTelemetryRepository,
    TaskStateService,
    FakeProvenanceRepository,
]:
    repo = _InMemoryTelemetryRepository(should_fail=db_should_fail)
    task_repo = _FakeTaskStateRepository()
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)
    task_service = TaskStateService(task_repo, provenance_recorder=prov_recorder)

    # Initialize T30 task state in CTS
    t30_task = CanonicalTaskState(
        task_id="task-t30",
        directive_id="dir-t30",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.IN_PROGRESS,
        cts_state={"tenant_id": tenant_id},
        governance_approved=True,
    )
    task_repo.states[t30_task.task_id] = t30_task

    normalizer = TelemetryNormalizer(repo)
    engine = OmnichannelTelemetryEngine(
        webhook_signing_secret=signing_secret,
        max_payload_bytes=262144,
        freshness_window_seconds=3600,
        max_future_skew_seconds=60,
        task_state_service=task_service,
        provenance_recorder=prov_recorder,
        telemetry_repository=repo,
        telemetry_normalizer=normalizer,
    )

    # Configure active T29 surfaces and readiness
    surfaces = [
        TelemetrySurface(
            channel="website",
            source_type=TelemetrySourceType.PIXEL,
            endpoint="/api/v1/telemetry/pixel",
            tenant_id=tenant_id,
            event_classes=[TelemetryEventType.TRAFFIC],
            is_active=True,
        ),
        TelemetrySurface(
            channel="website",
            source_type=TelemetrySourceType.CONVERSION,
            endpoint="/api/v1/telemetry/conversions",
            tenant_id=tenant_id,
            event_classes=[TelemetryEventType.CONVERSION, TelemetryEventType.CHECKOUT, TelemetryEventType.TRANSACTION],
            is_active=True,
        ),
        TelemetrySurface(
            channel="website",
            source_type=TelemetrySourceType.ERROR_LOG,
            endpoint="/api/v1/telemetry/errors",
            tenant_id=tenant_id,
            event_classes=[TelemetryEventType.ERROR],
            is_active=True,
        ),
        TelemetrySurface(
            channel="meta",
            source_type=TelemetrySourceType.WEBHOOK,
            endpoint="/api/v1/telemetry/webhooks/ads/meta",
            tenant_id=tenant_id,
            event_classes=[TelemetryEventType.AD_SPEND, TelemetryEventType.CONVERSION, TelemetryEventType.ROAS],
            is_active=True,
        ),
        TelemetrySurface(
            channel="google",
            source_type=TelemetrySourceType.WEBHOOK,
            endpoint="/api/v1/telemetry/webhooks/ads/google",
            tenant_id=tenant_id,
            event_classes=[TelemetryEventType.AD_SPEND, TelemetryEventType.CONVERSION, TelemetryEventType.ROAS],
            is_active=True,
        ),
        TelemetrySurface(
            channel="tiktok",
            source_type=TelemetrySourceType.WEBHOOK,
            endpoint="/api/v1/telemetry/webhooks/ads/tiktok",
            tenant_id=tenant_id,
            event_classes=[TelemetryEventType.AD_SPEND, TelemetryEventType.CONVERSION, TelemetryEventType.ROAS],
            is_active=True,
        ),
        TelemetrySurface(
            channel="instagram",
            source_type=TelemetrySourceType.WEBHOOK,
            endpoint="/api/v1/telemetry/webhooks/social/instagram",
            tenant_id=tenant_id,
            event_classes=[TelemetryEventType.SOCIAL_ENGAGEMENT, TelemetryEventType.TRAFFIC],
            is_active=True,
        ),
        TelemetrySurface(
            channel="x",
            source_type=TelemetrySourceType.WEBHOOK,
            endpoint="/api/v1/telemetry/webhooks/social/x",
            tenant_id=tenant_id,
            event_classes=[TelemetryEventType.SOCIAL_ENGAGEMENT, TelemetryEventType.TRAFFIC],
            is_active=True,
        ),
        TelemetrySurface(
            channel="youtube",
            source_type=TelemetrySourceType.WEBHOOK,
            endpoint="/api/v1/telemetry/webhooks/social/youtube",
            tenant_id=tenant_id,
            event_classes=[TelemetryEventType.SOCIAL_ENGAGEMENT, TelemetryEventType.TRAFFIC],
            is_active=True,
        ),
    ]

    for s in surfaces:
        engine.register_surface(s)

    if t29_ready:
        engine.register_readiness(
            OmnichannelTelemetryReadiness(
                readiness_id=f"readiness-{tenant_id}",
                tenant_id=tenant_id,
                is_ready=True,
                dependencies={"t26": "dep-1", "t27": "dep-2", "t28": "dep-3"},
                active_surfaces=surfaces,
                probes=[],
                blocked_reasons=[],
            )
        )

    return engine, repo, task_service, prov_repo


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


@pytest.mark.asyncio
async def test_t30_requires_t29_authoritative_readiness() -> None:
    """Live telemetry ingestion fails closed when T29 readiness is missing or marked unready."""
    engine, _, _, _ = _setup_t30_environment(tenant_id="tenant-alpha", t29_ready=False)

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=datetime.now(UTC),
        metrics={"pageviews": 1.0},
    )

    with pytest.raises(PolicyViolationError) as exc:
        await engine.ingest_live_telemetry(envelope)
    assert "T29 telemetry listener readiness is not satisfied" in str(exc.value)


@pytest.mark.asyncio
async def test_t30_rejects_unregistered_channel_or_bad_source() -> None:
    """Telemetry targeting an unapproved network or unregistered channel fails closed."""
    engine, _, _, _ = _setup_t30_environment(tenant_id="tenant-alpha")

    # Snapchat is not registered in active T29 surfaces
    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="snapchat",
        event_type=TelemetryEventType.AD_SPEND,
        occurred_at=datetime.now(UTC),
        metrics={"spend": 100.0},
    )

    with pytest.raises(PolicyViolationError) as exc:
        await engine.ingest_live_telemetry(envelope)
    assert "not an authorized active telemetry surface" in str(exc.value)


@pytest.mark.asyncio
async def test_t30_rejects_invalid_signature_or_unauthenticated_ingress() -> None:
    """Inbound webhooks with missing or altered HMAC-SHA256 signatures fail closed."""
    engine, _, _, _ = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret="secret_abc_123")

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="meta",
        event_type=TelemetryEventType.AD_SPEND,
        occurred_at=datetime.now(UTC),
        metrics={"spend": 250.0},
    )
    raw_body = json.dumps(envelope.model_dump(), default=str).encode("utf-8")

    # 1. Missing signature
    with pytest.raises(SignatureVerificationError):
        await engine.ingest_live_telemetry(envelope, raw_body=raw_body, signature=None)

    # 2. Forged signature
    with pytest.raises(SignatureVerificationError):
        await engine.ingest_live_telemetry(envelope, raw_body=raw_body, signature="sha256=forged_bad_signature")


@pytest.mark.asyncio
async def test_t30_rejects_tenant_mismatch_and_cross_tenant_access() -> None:
    """Events specifying an un-registered tenant ID raise AuthorizationError."""
    engine, _, _, _ = _setup_t30_environment(tenant_id="tenant-alpha")

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-rogue",
        channel="website",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=datetime.now(UTC),
        metrics={"pageviews": 1.0},
    )

    with pytest.raises(AuthorizationError) as exc:
        await engine.ingest_live_telemetry(envelope)
    assert "no registered active telemetry surfaces" in str(exc.value)


@pytest.mark.asyncio
async def test_t30_validates_payload_schema_and_size_bounds() -> None:
    """Oversized payloads (> 256KB) fail closed with PolicyViolationError."""
    engine, _, _, _ = _setup_t30_environment(tenant_id="tenant-alpha")

    oversized_data = "x" * (300 * 1024)  # 300 KB
    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=datetime.now(UTC),
        metrics={"pageviews": 1.0},
        payload={"large_blob": oversized_data},
    )

    with pytest.raises(PolicyViolationError) as exc:
        await engine.ingest_live_telemetry(envelope)
    assert "exceeds maximum permitted" in str(exc.value)


@pytest.mark.asyncio
async def test_t30_enforces_timestamp_freshness_window() -> None:
    """Stale events (> 1 hr) and future events (> 60s) fail closed."""
    engine, _, _, _ = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=None)

    # Stale event (2 hours ago)
    stale_envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=datetime.now(UTC) - timedelta(hours=2),
        metrics={"pageviews": 1.0},
    )
    with pytest.raises(PolicyViolationError) as exc:
        await engine.ingest_live_telemetry(stale_envelope)
    assert "is stale" in str(exc.value)

    # Future event (+ 5 minutes)
    future_envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=datetime.now(UTC) + timedelta(minutes=5),
        metrics={"pageviews": 1.0},
    )
    with pytest.raises(PolicyViolationError) as exc:
        await engine.ingest_live_telemetry(future_envelope)
    assert "is in the future" in str(exc.value)


@pytest.mark.asyncio
async def test_t30_ingests_and_persists_storefront_traffic_pixel() -> None:
    """Storefront pixel traffic pageviews are validated, normalized, and persisted in CDB."""
    engine, repo, task_service, prov_repo = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=None)

    event_time = datetime.now(UTC) - timedelta(minutes=5)
    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=event_time,
        account_id="store-us-01",
        metrics={"pageviews": 12.0, "unique_visitors": 8.0},
        payload={"url": "/products/flagship-item", "referrer": "https://google.com"},
    )

    persisted = await engine.ingest_live_telemetry(envelope)

    assert persisted.tenant_id == "tenant-alpha"
    assert persisted.channel == "website"
    assert persisted.event_type == TelemetryEventType.TRAFFIC
    assert persisted.metrics["pageviews"] == 12.0
    assert persisted.occurred_at == event_time
    assert persisted.received_at >= event_time

    # Verify presence in database repository
    in_db = await repo.get(persisted.event_id)
    assert in_db is not None
    assert in_db.event_id == persisted.event_id


@pytest.mark.asyncio
async def test_t30_ingests_and_persists_checkout_and_transactions() -> None:
    """Checkout and transaction conversion events are durably persisted with transaction identifiers."""
    engine, repo, _, _ = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=None)

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.CONVERSION,
        occurred_at=datetime.now(UTC) - timedelta(minutes=2),
        account_id="store-us-01",
        source_id="order-txn-9876",
        correlation_id="corr-sess-1234",
        metrics={"order_value": 249.99, "items_count": 3.0, "tax": 20.0},
        payload={"action": "checkout_completed", "order_id": "order-txn-9876"},
    )

    persisted = await engine.ingest_live_telemetry(envelope)

    assert persisted.event_type == TelemetryEventType.CONVERSION
    assert persisted.source_id == "order-txn-9876"
    assert persisted.correlation_id == "corr-sess-1234"
    assert persisted.metrics["order_value"] == 249.99

    stored = await repo.get(persisted.event_id)
    assert stored is not None
    assert stored.payload["order_id"] == "order-txn-9876"


@pytest.mark.asyncio
async def test_t30_ingests_and_persists_application_errors() -> None:
    """Storefront and application error-log telemetry events are persisted into CDB."""
    engine, repo, _, _ = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=None)

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.ERROR,
        occurred_at=datetime.now(UTC),
        metrics={"error_count": 1.0, "status_code": 500.0},
        payload={"error_message": "Checkout service unavailable", "component": "payment_gateway"},
    )

    persisted = await engine.ingest_live_telemetry(envelope)
    assert persisted.event_type == TelemetryEventType.ERROR
    assert persisted.metrics["status_code"] == 500.0

    in_db = await repo.get(persisted.event_id)
    assert in_db is not None
    assert in_db.payload["component"] == "payment_gateway"


@pytest.mark.asyncio
async def test_t30_ingests_and_persists_ad_performance_webhooks() -> None:
    """Activated Meta, Google, and TikTok ad performance webhooks are authenticated and persisted."""
    secret = "ad_signing_key_456"
    engine, repo, _, _ = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=secret)

    for channel in ("meta", "google", "tiktok"):
        envelope = WebhookIngestEnvelope(
            tenant_id="tenant-alpha",
            channel=channel,
            event_type=TelemetryEventType.AD_SPEND,
            occurred_at=datetime.now(UTC) - timedelta(minutes=1),
            metrics={"spend": 1250.0, "impressions": 45000.0, "clicks": 1800.0},
            payload={"campaign_id": f"{channel}-camp-100"},
        )
        raw_body = json.dumps(envelope.model_dump(), default=str).encode("utf-8")
        sig = _sign_payload(raw_body, secret)

        persisted = await engine.ingest_live_telemetry(envelope, raw_body=raw_body, signature=sig)
        assert persisted.channel == channel
        assert persisted.metrics["spend"] == 1250.0

        in_db = await repo.get(persisted.event_id)
        assert in_db is not None


@pytest.mark.asyncio
async def test_t30_ingests_and_persists_social_engagement_webhooks() -> None:
    """Activated Instagram, X, and YouTube social engagement signals are authenticated and persisted."""
    secret = "soc_signing_key_789"
    engine, repo, _, _ = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=secret)

    for channel in ("instagram", "x", "youtube"):
        envelope = WebhookIngestEnvelope(
            tenant_id="tenant-alpha",
            channel=channel,
            event_type=TelemetryEventType.SOCIAL_ENGAGEMENT,
            occurred_at=datetime.now(UTC) - timedelta(minutes=3),
            metrics={"likes": 320.0, "shares": 45.0, "comments": 28.0},
            payload={"post_id": f"{channel}-post-555"},
        )
        raw_body = json.dumps(envelope.model_dump(), default=str).encode("utf-8")
        sig = _sign_payload(raw_body, secret)

        persisted = await engine.ingest_live_telemetry(envelope, raw_body=raw_body, signature=sig)
        assert persisted.channel == channel
        assert persisted.metrics["likes"] == 320.0

        in_db = await repo.get(persisted.event_id)
        assert in_db is not None


@pytest.mark.asyncio
async def test_t30_idempotent_deduplication_on_webhook_retry() -> None:
    """Replaying an identical transaction or webhook with the same idempotency key does not insert duplicate rows."""
    engine, repo, _, _ = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=None)

    idempotency_key = f"idemp-order-{uuid.uuid4()}"
    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.CONVERSION,
        occurred_at=datetime.now(UTC) - timedelta(minutes=1),
        idempotency_key=idempotency_key,
        metrics={"order_value": 399.0},
        payload={"order_id": "ORD-5555"},
    )

    # Initial delivery
    first_event = await engine.ingest_live_telemetry(envelope)
    assert first_event is not None

    all_initial = await repo.list_by_tenant("tenant-alpha")
    assert len(all_initial) == 1

    # Webhook retry with identical idempotency key
    retry_event = await engine.ingest_live_telemetry(envelope)

    # Must return existing event without inserting a second row in CDB
    assert retry_event.event_id == first_event.event_id
    all_after_retry = await repo.list_by_tenant("tenant-alpha")
    assert len(all_after_retry) == 1


@pytest.mark.asyncio
async def test_t30_scrubs_sensitive_financial_and_pii_data() -> None:
    """Credit card numbers, CVVs, passwords, and tokens in payloads are scrubbed before persistence."""
    engine, repo, _, prov_repo = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=None)

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.CONVERSION,
        occurred_at=datetime.now(UTC),
        metrics={"order_value": 50.0},
        payload={
            "order_id": "ORD-1234",
            "card_number": "4111-2222-3333-4444",
            "cvv": "999",
            "access_token": "bearer_super_secret_token",
            "customer_password": "PlaintextPassword123!",
            "customer_note": "Gift delivery",
        },
    )

    persisted = await engine.ingest_live_telemetry(envelope)

    # Check that persisted payload in CDB is sanitized
    assert persisted.payload["order_id"] == "ORD-1234"
    assert persisted.payload["customer_note"] == "Gift delivery"
    assert persisted.payload["card_number"] == "[REDACTED]"
    assert persisted.payload["cvv"] == "[REDACTED]"
    assert persisted.payload["access_token"] == "[REDACTED]"
    assert persisted.payload["customer_password"] == "[REDACTED]"

    # Verify repository document does not store secrets
    stored = await repo.get(persisted.event_id)
    assert stored is not None
    doc_str = str(stored.model_dump()).lower()
    assert "4111-2222-3333-4444" not in doc_str
    assert "plaintextpassword123!" not in doc_str
    assert "bearer_super_secret_token" not in doc_str


@pytest.mark.asyncio
async def test_t30_database_failure_fails_explicitly() -> None:
    """Database failures raise RepositoryError and never falsely report success."""
    engine, _, _, _ = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=None, db_should_fail=True)

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=datetime.now(UTC),
        metrics={"pageviews": 1.0},
    )

    with pytest.raises(RepositoryError) as exc:
        await engine.ingest_live_telemetry(envelope)
    assert "Simulated database connection failure" in str(exc.value)


@pytest.mark.asyncio
async def test_t30_batch_partial_failure_handling() -> None:
    """Batch ingestion isolates failures: valid envelopes succeed and invalid envelopes report diagnostics."""
    engine, repo, _, _ = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=None)

    valid_envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=datetime.now(UTC) - timedelta(minutes=1),
        metrics={"pageviews": 5.0},
    )

    stale_envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=datetime.now(UTC) - timedelta(hours=3),  # Stale
        metrics={"pageviews": 2.0},
    )

    unregistered_channel_envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="unsupported_network",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=datetime.now(UTC),
        metrics={"pageviews": 1.0},
    )

    batch_response = await engine.ingest_batch(
        "tenant-alpha",
        [valid_envelope, stale_envelope, unregistered_channel_envelope],
    )

    assert batch_response.total_received == 3
    assert batch_response.total_succeeded == 1
    assert batch_response.total_failed == 2

    # Verify first succeeded
    assert batch_response.results[0].success is True
    assert batch_response.results[0].event_id is not None

    # Verify second failed on staleness
    assert batch_response.results[1].success is False
    assert "is stale" in str(batch_response.results[1].error)

    # Verify third failed on unapproved surface
    assert batch_response.results[2].success is False
    assert "not an authorized active telemetry surface" in str(batch_response.results[2].error)

    # Verify CDB has exactly 1 record
    all_events = await repo.list_by_tenant("tenant-alpha")
    assert len(all_events) == 1


@pytest.mark.asyncio
async def test_t30_distinguishes_event_time_from_ingest_time() -> None:
    """occurred_at (event time) and received_at (ingest time) remain clearly distinguishable."""
    engine, _, _, _ = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=None)

    event_time = datetime.now(UTC) - timedelta(minutes=25)
    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=event_time,
        metrics={"pageviews": 1.0},
    )

    persisted = await engine.ingest_live_telemetry(envelope)

    assert persisted.occurred_at == event_time
    # received_at was captured at actual ingest time
    time_diff = (persisted.received_at - persisted.occurred_at).total_seconds()
    assert time_diff >= 1400.0  # ~25 minutes difference


@pytest.mark.asyncio
async def test_t30_updates_cts_state_and_records_provenance() -> None:
    """Successful ingestion updates T30 task CTS state and emits scrubbed audit provenance."""
    engine, repo, task_service, prov_repo = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=None)

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="website",
        event_type=TelemetryEventType.TRAFFIC,
        occurred_at=datetime.now(UTC),
        metrics={"pageviews": 10.0},
    )

    event = await engine.ingest_live_telemetry(envelope)

    # Check CTS state for task-t30
    task = await task_service.get_state("task-t30")
    assert "telemetry_ingestion" in task.cts_state
    assert task.cts_state["telemetry_ingestion"]["total_ingested"] == 1

    # Check provenance record
    records = await prov_repo.chain("tenant-alpha")
    ingest_records = [r for r in records if r.activity == "telemetry_event_ingested"]
    assert len(ingest_records) == 1
    assert ingest_records[0].entity_id == event.event_id
    assert ingest_records[0].metadata["channel"] == "website"


@pytest.mark.asyncio
async def test_t30_zero_t31_learning_or_attribution_execution() -> None:
    """T30 ingestion stores events in CDB but strictly avoids invoking T31 attribution or learning."""
    engine, repo, _, prov_repo = _setup_t30_environment(tenant_id="tenant-alpha", signing_secret=None)

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant-alpha",
        channel="meta",
        event_type=TelemetryEventType.ROAS,
        occurred_at=datetime.now(UTC),
        metrics={"roas": 4.5, "spend": 1000.0, "revenue": 4500.0},
    )

    persisted = await engine.ingest_live_telemetry(envelope)
    assert persisted.event_type == TelemetryEventType.ROAS

    # Assert zero T31 / learning loop provenance entries
    records = await prov_repo.chain("tenant-alpha")
    for r in records:
        assert "t31" not in r.activity.lower()
        assert "w_learn" not in r.agent.lower()
        assert "attribution" not in r.activity.lower()
        assert "memory_promotion" not in r.activity.lower()
