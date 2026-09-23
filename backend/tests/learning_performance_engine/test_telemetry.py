"""Unit tests for LP-04 Telemetry Foundation and LEARN-TELEMETRY specialist."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest

from app.agents.learning_performance_engine.subagents.telemetry import LearningTelemetryAgent
from app.integrations.sandbox.s_attr_core import validate_and_normalize_telemetry
from app.schemas.agent_contracts import TaskGrant
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.learning_performance import (
    LearningDatasetManifest,
    SpecialistStatus,
)


def _sample_events(tenant_id: str = "tenant-1") -> list[dict]:
    base_time = datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC)
    return [
        {
            "event_id": "ev-1",
            "tenant_id": tenant_id,
            "event_type": "traffic",
            "channel": "meta",
            "occurred_at": (base_time - timedelta(days=2)).isoformat(),
            "correlation_id": "user-123",
            "metrics": {"clicks": 1.0, "cost": 0.50},
        },
        {
            "event_id": "ev-2",
            "tenant_id": tenant_id,
            "event_type": "conversion",
            "channel": "meta",
            "occurred_at": (base_time - timedelta(days=1)).isoformat(),
            "correlation_id": "user-123",
            "metrics": {"order_value": 150.0, "revenue": 150.0},
        },
        {
            "event_id": "ev-3",
            "tenant_id": tenant_id,
            "event_type": "ad_spend",
            "channel": "meta",
            "occurred_at": (base_time - timedelta(days=1)).isoformat(),
            "metrics": {"spend": 100.0},
        },
    ]


def test_deterministic_normalization_and_content_hashing() -> None:
    events = _sample_events()
    payload = {
        "task_id": "task-1",
        "tenant_id": "tenant-1",
        "events": events,
        "window_start": "2026-09-01T00:00:00Z",
        "window_end": "2026-09-23T00:00:00Z",
    }

    res1 = validate_and_normalize_telemetry(payload)
    res2 = validate_and_normalize_telemetry(payload)

    assert res1["status"] == "complete"
    assert res1["dataset_hash"] == res2["dataset_hash"]
    assert res1["artifact_id"] == res2["artifact_id"]
    assert res1["row_count"] == 3


def test_cross_tenant_telemetry_fails_closed() -> None:
    events = _sample_events()
    events.append({
        "event_id": "ev-rogue",
        "tenant_id": "tenant-other",
        "event_type": "conversion",
        "channel": "google",
        "occurred_at": "2026-09-20T12:00:00Z",
    })

    payload = {
        "task_id": "task-1",
        "tenant_id": "tenant-1",
        "events": events,
    }

    res = validate_and_normalize_telemetry(payload)
    assert res["status"] == "failed"
    assert res["error_category"] == "tenant_boundary_violation"
    assert "Cross-tenant telemetry detected" in res["error"]


def test_deduplication_and_conflicting_duplicates() -> None:
    events = _sample_events()
    # Exact duplicate
    events.append(dict(events[0]))
    # Conflicting duplicate: same idempotency key but different metric value
    conflicting = dict(events[0])
    conflicting["event_id"] = "ev-conflict"
    conflicting["metrics"] = {"clicks": 5.0, "cost": 2.50}
    events.append(conflicting)

    payload = {
        "task_id": "task-1",
        "tenant_id": "tenant-1",
        "events": events,
    }

    res = validate_and_normalize_telemetry(payload)
    assert res["status"] == "complete"
    manifest = res["manifest"]
    assert manifest["duplicate_count"] == 2
    assert manifest["quarantine_count"] == 1  # conflicting one quarantined


def test_out_of_window_and_nonfinite_quarantined() -> None:
    events = _sample_events()
    # Out of window (too old)
    events.append({
        "event_id": "ev-ancient",
        "tenant_id": "tenant-1",
        "event_type": "traffic",
        "occurred_at": "2020-01-01T00:00:00Z",
    })
    # Nonfinite NaN metric
    events.append({
        "event_id": "ev-nan",
        "tenant_id": "tenant-1",
        "event_type": "traffic",
        "occurred_at": "2026-09-20T12:00:00Z",
        "metrics": {"spend": float("nan")},
    })

    payload = {
        "task_id": "task-1",
        "tenant_id": "tenant-1",
        "events": events,
        "window_start": "2026-09-15T00:00:00Z",
        "window_end": "2026-09-23T00:00:00Z",
    }

    res = validate_and_normalize_telemetry(payload)
    assert res["status"] == "complete"
    manifest = res["manifest"]
    assert manifest["quarantine_count"] >= 2


@pytest.mark.asyncio
async def test_learning_telemetry_agent_excludes_raw_rows() -> None:
    agent = LearningTelemetryAgent()
    grant = TaskGrant(
        task_id="task-learn-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="tenant-1"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    context = {
        "events": _sample_events(),
        "window_start": "2026-09-01T00:00:00Z",
        "window_end": "2026-09-23T00:00:00Z",
    }

    manifest, result = await agent.run(grant, context)

    assert manifest is not None
    assert isinstance(manifest, LearningDatasetManifest)
    assert result.status == SpecialistStatus.COMPLETE
    assert manifest.row_count == 3
    assert len(manifest.content_hash) == 64

    # Raw rows must not be present in result or manifest
    manifest_dump = manifest.model_dump(mode="json")
    assert "events" not in manifest_dump
    assert "raw_events" not in manifest_dump
    assert "user-123" not in str(manifest_dump)
    assert "user-123" not in str(result.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_learning_telemetry_agent_insufficient_evidence() -> None:
    agent = LearningTelemetryAgent()
    grant = TaskGrant(
        task_id="task-empty",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="tenant-1"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    context = {"events": []}

    manifest, result = await agent.run(grant, context)
    assert manifest is None
    assert result.status == SpecialistStatus.INSUFFICIENT_EVIDENCE
    assert result.insufficient_evidence_reason is not None
