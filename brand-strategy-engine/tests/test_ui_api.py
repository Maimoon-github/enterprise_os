"""Integration tests for the stage-wise UI API (sequential gating, state persistence, safety)."""

import base64

import pytest
from fastapi.testclient import TestClient

from src.runtime import api
from src.tools.browser_bridge import BrowserBridge

PAYLOAD = {
    "url": "https://alexchen.dev",
    "brand_name": "Alex Chen",
    "industry": "Distributed Systems",
    "mode": "Mode_A_Personal",
}


@pytest.fixture
def client(monkeypatch, sample_html):
    async def fake_fetch(self, url):
        return sample_html, 200

    monkeypatch.setattr(BrowserBridge, "fetch_page_response", fake_fetch)
    with TestClient(api.app) as c:
        yield c


def _create(client):
    r = client.post("/api/v1/session", json=PAYLOAD)
    assert r.status_code == 200, r.text
    return r.json()


def test_ui_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Agent 0" in r.text


def test_stage_zero_gate_rejects_empty_url(client):
    r = client.post("/api/v1/session", json={**PAYLOAD, "url": "   "})
    assert r.status_code == 400


def test_sequential_gating_blocks_out_of_order_stage(client):
    view = _create(client)
    sid = view["session_id"]
    assert view["next_stage"] == 1
    assert [s["status"] for s in view["stages"]] == ["ready"] + ["locked"] * 5
    for n in (2, 3, 6):
        assert client.post(f"/api/v1/session/{sid}/stage/{n}").status_code == 409
    # Gate rejection must not mutate canonical state
    assert client.get(f"/api/v1/session/{sid}").json()["current_stage"] == "Initialization"


def test_stage_by_stage_execution_and_persistence(client):
    sid = _create(client)["session_id"]
    for n in range(1, 6):
        view = client.post(f"/api/v1/session/{sid}/stage/{n}").json()
        assert view["stages"][n - 1]["status"] == "completed"
        assert view["stages"][n - 1]["attempts"][-1]["steps"], f"Stage {n} produced no ReAct trace"
        # re-running a completed stage is gated
        assert client.post(f"/api/v1/session/{sid}/stage/{n}").status_code == 409
    # State survives independent reads (tab switch / reload)
    assert client.get(f"/api/v1/session/{sid}").json() == client.get(f"/api/v1/session/{sid}").json()
    view = client.post(f"/api/v1/session/{sid}/stage/6").json()
    assert view["validation_report"]["status"] != "Pending"
    assert view["iteration_counter"] <= view["max_revision_loops"]
    assert api._SESSION_STATES[sid].session_id == sid  # UI mutates canonical MasterEngineState


def test_run_all_reaches_terminal_state_within_revision_ceiling(client):
    sid = _create(client)["session_id"]
    view = client.post(f"/api/v1/session/{sid}/run-all").json()
    view = client.get(f"/api/v1/session/{sid}").json()
    assert view["error"] is None, view["error"]
    assert not view["running"]
    assert view["current_stage"] == "Completed"
    assert view["next_stage"] is None
    assert view["iteration_counter"] <= view["max_revision_loops"]
    assert view["dossier"] is not None
    assert any(t["tool"] == "compile_strategy_dossier" for t in view["manager"]["telemetry"])


def test_document_upload_validation(client):
    bad = {"filename": "../../evil.exe", "content_b64": base64.b64encode(b"x").decode()}
    assert client.post("/api/v1/session", json={**PAYLOAD, "documents": [bad]}).status_code == 415
    badb64 = {"filename": "a.txt", "content_b64": "***not-base64***"}
    assert client.post("/api/v1/session", json={**PAYLOAD, "documents": [badb64]}).status_code == 400
    ok = {"filename": "../brief.txt", "content_b64": base64.b64encode(b"Brand brief: enterprise buyers.").decode()}
    r = client.post("/api/v1/session", json={**PAYLOAD, "documents": [ok]})
    assert r.status_code == 200


def test_unknown_session_and_screenshot_safety(client):
    assert client.get("/api/v1/session/nope").status_code == 404
    sid = _create(client)["session_id"]
    assert client.get(f"/api/v1/session/{sid}/evidence/..%2F..%2Fetc%2Fpasswd/screenshot").status_code == 404
