# pyright: reportMissingImports=false
"""End-to-End Integration Tests for UI Dashboard, API Bridge, and HitL Approval (TSK-11).

Validates:
1. FastAPI WebSocket real-time event streaming for node transitions and observations.
2. State pause at human_gate checkpoint and resumption via operator approval across thread IDs.
3. Live ObservationResult telemetry and CRO artifact visual endpoint serving.
4. Sole Strategy Engine authority enforcement (sandbox commands emitted exclusively via engine).
"""

import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from api.server import app, engine_graph


@pytest.fixture
def client():
    return TestClient(app)


def test_health_and_authority_containment(client):
    """Verify bridge health and sole engine authority model."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["authority"] == "sole_engine_containment"

    # Enforce that no raw or direct sandbox dispatch routes exist
    bad_routes = ["/api/sandbox/execute", "/api/sandbox/dispatch", "/sandbox/raw"]
    for route in bad_routes:
        r = client.post(route, json={"cmd": "whoami"})
        assert r.status_code == 404, f"Forbidden direct sandbox route exposed: {route}"


def test_websocket_telemetry_streaming_and_hitl_lifecycle(client):
    """Verify WebSocket connection, HitL suspension, approval resume, and observation streaming."""
    thread_id = "test-session-hitl-001"

    with client.websocket_connect(f"/ws/{thread_id}") as ws:
        # 1. Connection established greeting
        init_event = ws.receive_json()
        assert init_event["event"] == "connection_established"
        assert init_event["thread_id"] == thread_id

        # 2. Trigger Strategy Engine run with HitL gate enabled
        run_res = client.post(
            "/api/runs",
            json={
                "thread_id": thread_id,
                "goal": "Audit storefront and compute CAC/CLV",
                "brand_name": "AuraGlow Skincare",
                "target_url": "https://auraglow-store.com",
                "require_human_gate": True,
                "max_iterations": 3,
            },
        )
        assert run_res.status_code == 200
        assert run_res.json()["status"] == "queued"

        # 3. Stream events until HitL suspension at human_gate
        events = []
        hitl_paused = False
        for _ in range(10):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("event") == "hitl_interrupted":
                hitl_paused = True
                assert msg.get("node") == "human_gate"
                assert "current_command" in msg
                break

        assert hitl_paused, "Expected execution to pause at human_gate checkpoint"

        # Verify state snapshot via REST endpoint confirms pause
        state_res = client.get(f"/api/threads/{thread_id}/state")
        assert state_res.status_code == 200
        state_data = state_res.json()
        assert "human_gate" in state_data["next_nodes"]
        assert state_data["audit_metrics"]["roas"] > 0

        # 4. Operator approves action with feedback
        appr_res = client.post(
            f"/api/threads/{thread_id}/approve",
            json={
                "approved": True,
                "feedback": "Approved by QA Operator for sandbox execution.",
            },
        )
        assert appr_res.status_code == 200
        assert appr_res.json()["status"] == "resumed"

        # 5. Receive resumed event and subsequent sandbox observation telemetry
        resumed_received = False
        obs_received = False
        completed_received = False

        for _ in range(15):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("event") == "hitl_resumed":
                resumed_received = True
                assert msg.get("approved") is True
            elif msg.get("event") == "node_transition" and msg.get("node") == "sandbox_dispatch_node":
                obs_received = True
                assert msg.get("observation") is not None
                obs = msg["observation"]
                assert obs.get("command_type") is not None
                assert obs.get("status") in ("success", "ok")
            elif msg.get("event") == "run_completed":
                completed_received = True
                break

        assert resumed_received, "Expected hitl_resumed WebSocket event"
        assert obs_received, "Expected observation telemetry from sandbox dispatch"
        assert completed_received, "Expected run_completed event after resumption"

        # 6. Verify final thread state via REST endpoint
        final_state_res = client.get(f"/api/threads/{thread_id}/state")
        assert final_state_res.status_code == 200
        final_state = final_state_res.json()
        assert final_state["human_approved"] is True
        assert len(final_state["history"]) >= 1


def test_hitl_rejection_halts_execution(client):
    """Verify operator rejection at human_gate halts run execution."""
    thread_id = "test-session-reject-002"

    with client.websocket_connect(f"/ws/{thread_id}") as ws:
        _ = ws.receive_json()  # connection greeting

        client.post(
            "/api/runs",
            json={
                "thread_id": thread_id,
                "goal": "Audit storefront and test rejection",
                "require_human_gate": True,
            },
        )

        # Wait for hitl_interrupted
        for _ in range(10):
            msg = ws.receive_json()
            if msg.get("event") == "hitl_interrupted":
                break

        # Operator rejects
        client.post(
            f"/api/threads/{thread_id}/approve",
            json={"approved": False, "feedback": "Rejected: unapproved ad campaign."},
        )

        # Check state confirms rejection
        state_res = client.get(f"/api/threads/{thread_id}/state")
        assert state_res.status_code == 200
        assert state_res.json()["human_approved"] is False


def test_cro_artifact_endpoint(client):
    """Verify CRO visual artifact endpoint serves valid PNG visual telemetry."""
    res = client.get("/api/artifacts/home/gem/audit_shot.png")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) > 100
