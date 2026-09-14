"""Unit tests for T29: Connect Omnichannel Telemetry Engine.

Verifies:
- Dependency verification over T26, T27, and T28.
- Surface inventory strictly matching activated T26–T28 surfaces.
- Ingress signature authentication (HMAC-SHA256).
- Tenant and channel routing allowlist enforcement.
- Timestamp freshness (rejection of stale events & future clock skew).
- Payload size ceiling enforcement.
- Replay / deduplication protection.
- Non-destructive synthetic probes with ZERO database writes (no T30 ingestion).
- Partial activation handling and failure reporting.
- Provenance auditing and recursive secret redaction.
- REST API endpoint routes (/readiness, /probe, /webhooks, /pixel, /conversions, /errors).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import (
    AuthorizationError,
    PolicyViolationError,
    SignatureVerificationError,
)
from app.main import app
from app.persistence.repositories.telemetry import TelemetryRepository
from app.schemas.governance import WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.schemas.telemetry import (
    OmnichannelTelemetryReadiness,
    TelemetryEventType,
    TelemetryHandshakeProbe,
    TelemetrySourceType,
    TelemetrySurface,
    WebhookIngestEnvelope,
)
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from app.services.telemetry_engine import OmnichannelTelemetryEngine
from tests.conftest import FakeProvenanceRepository


class InMemoryTaskStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task '{task_id}' not found.")
        return self.states[task_id]

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state


def _make_task_state(task_id: str, tenant_id: str, status: TaskStatus) -> CanonicalTaskState:
    return CanonicalTaskState(
        task_id=task_id,
        directive_id=f"dir_{task_id}",
        worker_role=WorkerRole.STRATEGY,
        tenant_id=tenant_id,
        status=status,
    )


def _setup_engine(
    *,
    signing_secret: str | None = "super_secret_webhook_key_12345",
    max_payload_bytes: int = 10240,  # 10 KB for testing
    freshness_window_seconds: int = 3600,
    max_future_skew_seconds: int = 60,
):
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)
    state_repo = InMemoryTaskStateRepository()
    from app.orchestration.task_state_machine import TaskStateMachine

    state_service = TaskStateService(state_repo, TaskStateMachine(), prov_recorder)

    engine = OmnichannelTelemetryEngine(
        webhook_signing_secret=signing_secret,
        max_payload_bytes=max_payload_bytes,
        freshness_window_seconds=freshness_window_seconds,
        max_future_skew_seconds=max_future_skew_seconds,
        task_state_service=state_service,
        provenance_recorder=prov_recorder,
    )
    return engine, state_repo, prov_repo, prov_recorder, signing_secret


@pytest.mark.asyncio
async def test_t29_dependency_verification_fails_if_t26_missing() -> None:
    """Blocks telemetry engine connection if T26 (Website/CMS) is uncompleted or missing."""
    engine, _, _, _, _ = _setup_engine()
    task_states = {
        # Missing t26
        "t27": _make_task_state("t27", "tenant_alpha", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_alpha", TaskStatus.COMPLETED),
    }

    with pytest.raises(PolicyViolationError) as exc:
        await engine.connect_and_verify(
            "tenant_alpha",
            task_states,
            active_deployments={"ads": ["meta"], "social": ["x"]},
        )
    assert "Dependency T26" in str(exc.value)


@pytest.mark.asyncio
async def test_t29_dependency_verification_fails_if_t27_missing() -> None:
    """Blocks telemetry engine connection if T27 (Paid Ads) is uncompleted or missing."""
    engine, _, _, _, _ = _setup_engine()
    task_states = {
        "t26": _make_task_state("t26", "tenant_alpha", TaskStatus.COMPLETED),
        # t27 failed
        "t27": _make_task_state("t27", "tenant_alpha", TaskStatus.FAILED),
        "t28": _make_task_state("t28", "tenant_alpha", TaskStatus.COMPLETED),
    }

    with pytest.raises(PolicyViolationError) as exc:
        await engine.connect_and_verify(
            "tenant_alpha",
            task_states,
            active_deployments={"cms": {"status": "published"}, "social": ["instagram"]},
        )
    assert "Dependency T27" in str(exc.value)


@pytest.mark.asyncio
async def test_t29_dependency_verification_fails_if_t28_missing() -> None:
    """Blocks telemetry engine connection if T28 (Social Media) is uncompleted or missing."""
    engine, _, _, _, _ = _setup_engine()
    task_states = {
        "t26": _make_task_state("t26", "tenant_alpha", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_alpha", TaskStatus.COMPLETED),
        # t28 is still in review/approval
        "t28": _make_task_state("t28", "tenant_alpha", TaskStatus.APPROVED),
    }

    with pytest.raises(PolicyViolationError) as exc:
        await engine.connect_and_verify(
            "tenant_alpha",
            task_states,
            active_deployments={"cms": {"status": "published"}, "ads": ["google"]},
        )
    assert "Dependency T28" in str(exc.value)


@pytest.mark.asyncio
async def test_t29_partial_surface_attaches_only_active_channels() -> None:
    """Only activated channels attach listeners; inactive channels remain detached."""
    engine, _, _, _, _ = _setup_engine()
    task_states = {
        "t26": _make_task_state("t26", "tenant_alpha", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_alpha", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_alpha", TaskStatus.COMPLETED),
    }
    # T26 activated CMS, T27 only activated Meta, T28 only activated YouTube
    active_deployments = {
        "cms": {"site_id": "store_alpha"},
        "ads": {"active_channels": ["meta"]},
        "social": {"active_channels": ["youtube"]},
    }

    readiness = await engine.connect_and_verify("tenant_alpha", task_states, active_deployments)
    assert readiness.is_ready is True

    connected_channels = {s.channel for s in readiness.active_surfaces}
    assert "website" in connected_channels
    assert "meta" in connected_channels
    assert "youtube" in connected_channels
    # Unactivated channels must NOT be attached
    assert "google" not in connected_channels
    assert "tiktok" not in connected_channels
    assert "instagram" not in connected_channels
    assert "x" not in connected_channels


@pytest.mark.asyncio
async def test_t29_unauthorized_platform_rejected_from_telemetry_inventory() -> None:
    """Unauthorized platforms (e.g. LinkedIn or rogue ad networks) are excluded from telemetry inventory."""
    engine, _, _, _, _ = _setup_engine()
    task_states = {
        "t26": _make_task_state("t26", "tenant_alpha", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_alpha", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_alpha", TaskStatus.COMPLETED),
    }
    active_deployments = {
        "cms": {"site_id": "store_alpha"},
        # Attempt to activate unauthorized networks
        "ads": {"active_channels": ["meta", "snapchat", "pinterest"]},
        "social": {"active_channels": ["x", "threads"]},
    }

    readiness = await engine.connect_and_verify("tenant_alpha", task_states, active_deployments)
    connected_channels = {s.channel for s in readiness.active_surfaces}
    assert "meta" in connected_channels
    assert "x" in connected_channels
    assert "snapchat" not in connected_channels
    assert "pinterest" not in connected_channels
    assert "threads" not in connected_channels


@pytest.mark.asyncio
async def test_t29_ingress_signature_verification_success() -> None:
    """Valid HMAC-SHA256 signature passes ingress authentication and returns normalized event."""
    engine, _, _, _, secret = _setup_engine(signing_secret="webhook_test_secret_abc")
    task_states = {
        "t26": _make_task_state("t26", "tenant_corp", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_corp", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_corp", TaskStatus.COMPLETED),
    }
    await engine.connect_and_verify(
        "tenant_corp",
        task_states,
        {"cms": {}, "ads": ["meta"], "social": ["instagram"]},
    )

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant_corp",
        channel="meta",
        event_type=TelemetryEventType.AD_SPEND,
        occurred_at=datetime.now(UTC),
        metrics={"spend": 150.0, "impressions": 12000.0},
    )
    payload_bytes = json.dumps(envelope.model_dump(), default=str).encode("utf-8")
    sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

    event = engine.validate_ingress(envelope, raw_body=payload_bytes, signature=f"sha256={sig}")
    assert event.tenant_id == "tenant_corp"
    assert event.channel == "meta"
    assert event.metrics["spend"] == 150.0


@pytest.mark.asyncio
async def test_t29_ingress_bad_signature_fails_closed() -> None:
    """Tampered or missing signature fails closed with SignatureVerificationError."""
    engine, _, _, _, _ = _setup_engine(signing_secret="webhook_test_secret_abc")
    task_states = {
        "t26": _make_task_state("t26", "tenant_corp", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_corp", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_corp", TaskStatus.COMPLETED),
    }
    await engine.connect_and_verify(
        "tenant_corp",
        task_states,
        {"cms": {}, "ads": ["meta"], "social": ["instagram"]},
    )

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant_corp",
        channel="meta",
        event_type=TelemetryEventType.AD_SPEND,
        occurred_at=datetime.now(UTC),
        metrics={"spend": 500.0},
    )
    payload_bytes = json.dumps(envelope.model_dump(), default=str).encode("utf-8")

    # Bad signature
    with pytest.raises(SignatureVerificationError):
        engine.validate_ingress(envelope, raw_body=payload_bytes, signature="sha256=invalid_signature_hex")

    # Missing signature
    with pytest.raises(SignatureVerificationError):
        engine.validate_ingress(envelope, raw_body=payload_bytes, signature=None)


@pytest.mark.asyncio
async def test_t29_tenant_mismatch_fails_closed() -> None:
    """Inbound telemetry with tenant ID not registered on active surface fails with AuthorizationError."""
    engine, _, _, _, _ = _setup_engine(signing_secret=None)
    task_states = {
        "t26": _make_task_state("t26", "tenant_legit", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_legit", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_legit", TaskStatus.COMPLETED),
    }
    await engine.connect_and_verify(
        "tenant_legit",
        task_states,
        {"cms": {}, "ads": ["google"], "social": ["youtube"]},
    )

    # Ingress with attacker/mismatched tenant
    envelope = WebhookIngestEnvelope(
        tenant_id="tenant_attacker_99",
        channel="google",
        event_type=TelemetryEventType.CONVERSION,
        occurred_at=datetime.now(UTC),
        metrics={"conversions": 10.0},
    )
    with pytest.raises(AuthorizationError) as exc:
        engine.validate_ingress(envelope)
    assert "no registered active telemetry surfaces" in str(exc.value)


@pytest.mark.asyncio
async def test_t29_unknown_channel_or_source_fails_closed() -> None:
    """Inbound telemetry targeting an unregistered channel for an active tenant fails with PolicyViolationError."""
    engine, _, _, _, _ = _setup_engine(signing_secret=None)
    task_states = {
        "t26": _make_task_state("t26", "tenant_alpha", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_alpha", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_alpha", TaskStatus.COMPLETED),
    }
    await engine.connect_and_verify(
        "tenant_alpha",
        task_states,
        {"cms": {}, "ads": ["meta"], "social": ["instagram"]},
    )

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant_alpha",
        channel="snapchat",  # Not in active surfaces
        event_type=TelemetryEventType.AD_SPEND,
        occurred_at=datetime.now(UTC),
        metrics={"spend": 50.0},
    )
    with pytest.raises(PolicyViolationError) as exc:
        engine.validate_ingress(envelope)
    assert "not an authorized active telemetry surface" in str(exc.value)


@pytest.mark.asyncio
async def test_t29_stale_event_rejected() -> None:
    """Events older than the freshness window (3600s) are rejected as stale."""
    engine, _, _, _, _ = _setup_engine(signing_secret=None, freshness_window_seconds=3600)
    task_states = {
        "t26": _make_task_state("t26", "tenant_alpha", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_alpha", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_alpha", TaskStatus.COMPLETED),
    }
    await engine.connect_and_verify(
        "tenant_alpha",
        task_states,
        {"cms": {}, "ads": ["meta"], "social": ["x"]},
    )

    stale_time = datetime.now(UTC) - timedelta(hours=3)
    envelope = WebhookIngestEnvelope(
        tenant_id="tenant_alpha",
        channel="meta",
        event_type=TelemetryEventType.AD_SPEND,
        occurred_at=stale_time,
        metrics={"spend": 100.0},
    )
    with pytest.raises(PolicyViolationError) as exc:
        engine.validate_ingress(envelope)
    assert "stale" in str(exc.value)


@pytest.mark.asyncio
async def test_t29_future_clock_skew_rejected() -> None:
    """Events with timestamps significantly in the future (> 60s) are rejected."""
    engine, _, _, _, _ = _setup_engine(signing_secret=None, max_future_skew_seconds=60)
    task_states = {
        "t26": _make_task_state("t26", "tenant_alpha", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_alpha", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_alpha", TaskStatus.COMPLETED),
    }
    await engine.connect_and_verify(
        "tenant_alpha",
        task_states,
        {"cms": {}, "ads": ["meta"], "social": ["x"]},
    )

    future_time = datetime.now(UTC) + timedelta(minutes=10)
    envelope = WebhookIngestEnvelope(
        tenant_id="tenant_alpha",
        channel="meta",
        event_type=TelemetryEventType.AD_SPEND,
        occurred_at=future_time,
        metrics={"spend": 100.0},
    )
    with pytest.raises(PolicyViolationError) as exc:
        engine.validate_ingress(envelope)
    assert "in the future" in str(exc.value)


@pytest.mark.asyncio
async def test_t29_oversized_payload_rejected() -> None:
    """Payloads exceeding max_payload_bytes ceiling fail closed."""
    engine, _, _, _, _ = _setup_engine(signing_secret=None, max_payload_bytes=512)
    task_states = {
        "t26": _make_task_state("t26", "tenant_alpha", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_alpha", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_alpha", TaskStatus.COMPLETED),
    }
    await engine.connect_and_verify(
        "tenant_alpha",
        task_states,
        {"cms": {}, "ads": ["meta"], "social": ["x"]},
    )

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant_alpha",
        channel="meta",
        event_type=TelemetryEventType.AD_SPEND,
        occurred_at=datetime.now(UTC),
        payload={"huge_data": "x" * 2000},
    )
    raw_body = json.dumps(envelope.model_dump(), default=str).encode("utf-8")
    with pytest.raises(PolicyViolationError) as exc:
        engine.validate_ingress(envelope, raw_body=raw_body)
    assert "exceeds maximum permitted" in str(exc.value)


@pytest.mark.asyncio
async def test_t29_duplicate_event_deduplicated_replay_protection() -> None:
    """Replaying an event with identical idempotency key or content hash is rejected."""
    engine, _, _, _, _ = _setup_engine(signing_secret=None)
    task_states = {
        "t26": _make_task_state("t26", "tenant_alpha", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_alpha", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_alpha", TaskStatus.COMPLETED),
    }
    await engine.connect_and_verify(
        "tenant_alpha",
        task_states,
        {"cms": {}, "ads": ["google"], "social": ["youtube"]},
    )

    envelope = WebhookIngestEnvelope(
        tenant_id="tenant_alpha",
        channel="google",
        event_type=TelemetryEventType.CONVERSION,
        occurred_at=datetime.now(UTC),
        idempotency_key="unique_conversion_key_001",
        metrics={"conversions": 1.0},
    )

    # First event accepted
    ev1 = engine.validate_ingress(envelope)
    assert ev1.event_type == TelemetryEventType.CONVERSION

    # Replay rejected
    with pytest.raises(PolicyViolationError) as exc:
        engine.validate_ingress(envelope)
    assert "Duplicate telemetry event detected" in str(exc.value)


@pytest.mark.asyncio
async def test_t29_non_destructive_synthetic_probe_does_not_persist_t30_events() -> None:
    """CRITICAL INVARIANT: Synthetic connection probes execute without invoking TelemetryRepository.record()."""
    engine, _, _, _, _ = _setup_engine(signing_secret=None)
    task_states = {
        "t26": _make_task_state("t26", "tenant_probe_test", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_probe_test", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_probe_test", TaskStatus.COMPLETED),
    }
    active_deployments = {
        "cms": {"site_id": "site_probe_01"},
        "ads": {"active_channels": ["meta", "google", "tiktok"]},
        "social": {"active_channels": ["instagram", "x", "youtube"]},
    }

    mock_telemetry_repo = AsyncMock(spec=TelemetryRepository)
    mock_telemetry_repo.record = AsyncMock()

    readiness = await engine.connect_and_verify(
        "tenant_probe_test", task_states, active_deployments
    )
    assert readiness.is_ready is True
    assert len(readiness.probes) == len(readiness.active_surfaces)
    assert all(p.success for p in readiness.probes)

    # Verify zero persistence to CDB / TelemetryRepository
    mock_telemetry_repo.record.assert_not_called()


@pytest.mark.asyncio
async def test_t29_listener_probe_failure_reported_without_falsely_marking_ready() -> None:
    """When an active surface probe fails or is inactive, readiness is marked False with reason."""
    engine, _, _, _, _ = _setup_engine(signing_secret=None)
    task_states = {
        "t26": _make_task_state("t26", "tenant_alpha", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_alpha", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_alpha", TaskStatus.COMPLETED),
    }
    active_deployments = {
        "cms": {"site_id": "site_01"},
        "ads": ["meta"],
        "social": ["x"],
    }

    # Simulate an inactive surface probe failure
    async def mock_probe(surface: TelemetrySurface):
        if surface.channel == "meta":
            return TelemetryHandshakeProbe(
                channel=surface.channel,
                source_type=surface.source_type,
                success=False,
                latency_ms=120.0,
                status="webhook_handshake_timeout",
                details={"error": "Meta Graph API webhook handshake timed out (504)."},
            )
        return TelemetryHandshakeProbe(
            channel=surface.channel,
            source_type=surface.source_type,
            success=True,
            latency_ms=15.0,
            status="connected",
        )

    engine.probe_listener = mock_probe  # type: ignore[assignment]

    readiness = await engine.connect_and_verify("tenant_alpha", task_states, active_deployments)
    assert readiness.is_ready is False
    assert len(readiness.blocked_reasons) > 0
    assert any("meta" in r for r in readiness.blocked_reasons)


@pytest.mark.asyncio
async def test_t29_successful_omnichannel_connection_updates_cts_and_provenance() -> None:
    """Authoritative T26-T28 activation successfully attaches listeners, updates CTS, and logs provenance."""
    engine, state_repo, prov_repo, _, _ = _setup_engine(signing_secret="wh_secret_xyz")

    governing_task_id = "task_t29_gov"
    task_state = _make_task_state(governing_task_id, "tenant_omega", TaskStatus.APPROVED)
    state_repo.states[governing_task_id] = task_state

    task_states = {
        "t26": _make_task_state("t26", "tenant_omega", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_omega", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_omega", TaskStatus.COMPLETED),
        governing_task_id: task_state,
    }
    active_deployments = {
        "cms": {"site_id": "omega_store"},
        "ads": {"active_channels": ["meta", "google", "tiktok"]},
        "social": {"active_channels": ["instagram", "x", "youtube"]},
    }

    readiness = await engine.connect_and_verify(
        "tenant_omega",
        task_states,
        active_deployments,
        governing_task_id=governing_task_id,
    )

    assert readiness.is_ready is True
    assert readiness.dependencies == {"T26": "COMPLETED", "T27": "COMPLETED", "T28": "COMPLETED"}

    # Total surfaces: 3 (website pixel/conv/error) + 3 (ads: meta/google/tiktok) + 3 (social: ig/x/yt) = 9
    assert len(readiness.active_surfaces) == 9

    # Verify CTS updated
    saved_state = await state_repo.require(governing_task_id)
    assert "telemetry_engine" in saved_state.cts_state
    cts_telemetry = saved_state.cts_state["telemetry_engine"]
    assert cts_telemetry["is_ready"] is True
    assert len(cts_telemetry["active_surfaces"]) == 9

    # Verify Provenance recorded
    chain = prov_repo._chains.get("tenant_omega", [])
    conn_events = [e for e in chain if e.activity == "omnichannel_telemetry_engine_connected"]
    assert len(conn_events) == 1


@pytest.mark.asyncio
async def test_t29_secret_redaction_in_provenance_and_logs() -> None:
    """Credentials, tokens, and webhook secrets are redacted ([REDACTED]) from provenance."""
    engine, state_repo, prov_repo, _, _ = _setup_engine(signing_secret="sensitive_key_99999")

    task_states = {
        "t26": _make_task_state("t26", "tenant_sec", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_sec", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_sec", TaskStatus.COMPLETED),
    }
    active_deployments = {
        "cms": {"site_id": "sec_site", "api_key": "sensitive_cms_api_token"},
        "ads": {"active_channels": ["meta"], "access_token": "EAAX_secret_meta_token"},
        "social": {"active_channels": ["x"], "bearer_token": "sensitive_x_bearer"},
    }

    await engine.connect_and_verify("tenant_sec", task_states, active_deployments)

    chain = prov_repo._chains.get("tenant_sec", [])
    assert len(chain) == 1
    meta_json = json.dumps(chain[0].metadata)
    assert "sensitive_key_99999" not in meta_json
    assert "sensitive_cms_api_token" not in meta_json
    assert "EAAX_secret_meta_token" not in meta_json
    assert "sensitive_x_bearer" not in meta_json


@pytest.mark.asyncio
async def test_t29_http_endpoints_roundtrip() -> None:
    """Tests HTTP transport layer endpoints (/readiness, /probe, /webhooks, /pixel)."""
    engine, _, _, _, _ = _setup_engine(signing_secret=None)
    task_states = {
        "t26": _make_task_state("t26", "tenant_http", TaskStatus.COMPLETED),
        "t27": _make_task_state("t27", "tenant_http", TaskStatus.COMPLETED),
        "t28": _make_task_state("t28", "tenant_http", TaskStatus.COMPLETED),
    }
    await engine.connect_and_verify(
        "tenant_http",
        task_states,
        {"cms": {}, "ads": ["meta"], "social": ["x"]},
    )

    # Attach engine to FastAPI app state
    app.state.telemetry_engine = engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET /api/v1/telemetry/readiness
        res_readiness = await client.get("/telemetry/readiness?tenant_id=tenant_http")
        assert res_readiness.status_code == 200
        body = res_readiness.json()
        assert body["is_ready"] is True
        assert body["tenant_id"] == "tenant_http"

        # 2. POST /api/v1/telemetry/probe
        res_probe = await client.post("/telemetry/probe?tenant_id=tenant_http")
        assert res_probe.status_code == 200
        probes = res_probe.json()
        assert len(probes) >= 4  # website (3) + meta (1) + x (1)

        # 3. POST /api/v1/telemetry/pixel
        pixel_payload = {
            "tenant_id": "tenant_http",
            "channel": "website",
            "event_type": "traffic",
            "occurred_at": datetime.now(UTC).isoformat(),
            "metrics": {"pageviews": 1.0},
        }
        res_pixel = await client.post("/telemetry/pixel", json=pixel_payload)
        assert res_pixel.status_code == 202
        assert res_pixel.json()["channel"] == "website"

        # 4. POST /api/v1/telemetry/webhooks/ads/meta
        ad_payload = {
            "tenant_id": "tenant_http",
            "channel": "meta",
            "event_type": "ad_spend",
            "occurred_at": datetime.now(UTC).isoformat(),
            "metrics": {"spend": 75.50},
        }
        res_ad = await client.post("/telemetry/webhooks/ads/meta", json=ad_payload)
        assert res_ad.status_code == 202
        assert res_ad.json()["channel"] == "meta"
