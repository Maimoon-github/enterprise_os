import json
import uuid
import pytest
from app.core.rbac import UserRole
from app.core.security import create_access_token
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_chat_session_lifecycle():
    transport = ASGITransport(app=app)
    admin_token = create_access_token({"sub": "admin_test_1", "email": "admin@ex.com", "role": UserRole.ADMIN.value})
    headers = {"Authorization": f"Bearer {admin_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Create chat session
        create_res = await ac.post(
            "/api/v1/chat/sessions",
            headers=headers,
            json={"title": "Q4 Strategy Discussion", "project_id": "proj_1"},
        )
        assert create_res.status_code == 201
        session_data = create_res.json()
        assert session_data["title"] == "Q4 Strategy Discussion"
        assert session_data["is_pinned"] is False
        session_id = session_data["id"]

        # 2. List chat sessions
        list_res = await ac.get("/api/v1/chat/sessions", headers=headers)
        assert list_res.status_code == 200
        sessions = list_res.json()
        assert any(s["id"] == session_id for s in sessions)

        # 3. Update / Pin chat session
        patch_res = await ac.patch(
            f"/api/v1/chat/sessions/{session_id}",
            headers=headers,
            json={"is_pinned": True, "title": "Updated Q4 Strategy"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["is_pinned"] is True
        assert patch_res.json()["title"] == "Updated Q4 Strategy"

        # 4. Get chat session details
        get_res = await ac.get(f"/api/v1/chat/sessions/{session_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["is_pinned"] is True
        assert "messages" in get_res.json()

        # 5. Delete session
        del_res = await ac.delete(f"/api/v1/chat/sessions/{session_id}", headers=headers)
        assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_chat_message_orchestrator_wiring():
    transport = ASGITransport(app=app)
    admin_token = create_access_token({"sub": "admin_test_2", "email": "admin2@ex.com", "role": UserRole.ADMIN.value})
    headers = {"Authorization": f"Bearer {admin_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create session
        session_res = await ac.post(
            "/api/v1/chat/sessions",
            headers=headers,
            json={"title": "New Orchestrator Chat"},
        )
        session_id = session_res.json()["id"]

        # Send non-streaming command
        msg_res = await ac.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=headers,
            json={
                "content": "Synthesize a multi-platform launch plan for brand awareness.",
                "stream": False,
            },
        )
        assert msg_res.status_code == 200
        msg_data = msg_res.json()
        assert msg_data["role"] == "assistant"
        assert msg_data["run_id"] is not None
        assert "Orchestrator received command" in msg_data["content"]

        # Verify messages history
        detail_res = await ac.get(f"/api/v1/chat/sessions/{session_id}", headers=headers)
        assert detail_res.status_code == 200
        messages = detail_res.json()["messages"]
        assert len(messages) >= 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_platform_connection_encryption_and_masking():
    transport = ASGITransport(app=app)
    admin_token = create_access_token({"sub": "admin_test_3", "email": "admin3@ex.com", "role": UserRole.ADMIN.value})
    viewer_token = create_access_token({"sub": "viewer_test", "email": "viewer@ex.com", "role": UserRole.VIEWER.value})

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Viewer forbidden from configuring credentials
        forbidden_res = await ac.put(
            "/api/v1/settings/platforms/linkedin",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"client_id": "li_client_12345", "client_secret": "super_secret_key"},
        )
        assert forbidden_res.status_code == 403

        # Admin configures credentials
        put_res = await ac.put(
            "/api/v1/settings/platforms/linkedin",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "client_id": "li_client_123456",
                "client_secret": "raw_sensitive_secret_never_leak",
                "access_token": "oauth_token_raw_value",
                "account_name": "Apex LinkedIn HQ",
            },
        )
        assert put_res.status_code == 200
        conn_data = put_res.json()
        assert conn_data["platform"] == "linkedin"
        assert conn_data["is_connected"] is True
        # Plaintext secrets must NEVER be returned
        assert "raw_sensitive_secret_never_leak" not in json.dumps(conn_data)
        assert "oauth_token_raw_value" not in json.dumps(conn_data)
        assert conn_data["masked_client_id"] == "li_***56"

        # Test Decryption Harness
        test_res = await ac.post(
            "/api/v1/settings/platforms/linkedin/test",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert test_res.status_code == 200
        assert test_res.json()["is_valid"] is True

        # Disconnect platform
        del_res = await ac.delete(
            "/api/v1/settings/platforms/linkedin",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_analytics_empty_state_contract():
    transport = ASGITransport(app=app)
    admin_token = create_access_token({"sub": "admin_test_4", "email": "admin4@ex.com", "role": UserRole.ADMIN.value})
    headers = {"Authorization": f"Bearer {admin_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Check channels status (8 supported platforms)
        channels_res = await ac.get("/api/v1/analytics/channels", headers=headers)
        assert channels_res.status_code == 200
        channels = channels_res.json()
        assert len(channels) == 8
        platforms = [c["platform"] for c in channels]
        assert "linkedin" in platforms
        assert "x" in platforms
        assert "youtube" in platforms

        # Check KPIs with a non-existent brand_id to verify dynamic 0-state without fake fixtures
        dummy_brand_id = uuid.uuid4()
        kpi_res = await ac.get(f"/api/v1/analytics/kpis?brand_id={dummy_brand_id}", headers=headers)
        assert kpi_res.status_code == 200
        kpi_data = kpi_res.json()
        assert kpi_data["impressions_total"] == 0
        assert kpi_data["clicks_total"] == 0
        assert kpi_data["ctr_average"] == 0.0
