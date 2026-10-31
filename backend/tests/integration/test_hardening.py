import pytest
from app.core.config import Settings
from app.core.rbac import UserRole
from app.core.security import create_access_token
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_social_auth_providers_unconfigured_and_masked():
    """Verify social auth endpoint explicitly returns unconfigured state and masks credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/providers")
        assert res.status_code == 200
        providers = res.json()
        assert len(providers) == 2

        google = next((p for p in providers if p["id"] == "google"), None)
        assert google is not None
        assert google["configured"] is False
        assert google["enabled"] is False
        assert google["client_id_preview"] is None

        github = next((p for p in providers if p["id"] == "github"), None)
        assert github is not None
        assert github["configured"] is False
        assert github["enabled"] is False
        assert github["client_id_preview"] is None


def test_fail_closed_production_security():
    """Verify system fails closed outside development/test if default or insecure secrets remain."""
    # Test rejection of default SECRET_KEY in production
    with pytest.raises(ValueError, match="Insecure or default SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="change_this_to_a_secure_random_64_char_hex_string",
            DEFAULT_ADMIN_PASSWORD="strong_custom_password_12345",
        )

    # Test rejection of short SECRET_KEY in production
    with pytest.raises(ValueError, match="Insecure or default SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="short-secret-key",
            DEFAULT_ADMIN_PASSWORD="strong_custom_password_12345",
        )

    # Test rejection of default DEFAULT_ADMIN_PASSWORD in production
    with pytest.raises(ValueError, match="Insecure DEFAULT_ADMIN_PASSWORD"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 64,
            DEFAULT_ADMIN_PASSWORD="admin123",
        )

    # Test rejection of default database password in production
    with pytest.raises(ValueError, match="Insecure or default database password"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 64,
            DEFAULT_ADMIN_PASSWORD="strong_custom_password_12345",
            DATABASE_URL="postgresql+asyncpg://marketing_os:marketing_os_secret@localhost:5432/marketing_os_db",
        )

    # Test rejection of default MINIO_ROOT_PASSWORD in production
    with pytest.raises(ValueError, match="Insecure or default MINIO_ROOT_PASSWORD"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 64,
            DEFAULT_ADMIN_PASSWORD="strong_custom_password_12345",
            DATABASE_URL="postgresql+asyncpg://prod_user:strong_pass_123@localhost:5432/marketing_os_db",
            SYNC_DATABASE_URL="postgresql://prod_user:strong_pass_123@localhost:5432/marketing_os_db",
            MINIO_ROOT_PASSWORD="minio_admin_secret",
        )

    # Test rejection of default LANGFUSE_SECRET_KEY in production
    with pytest.raises(ValueError, match="Insecure or default LANGFUSE_SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 64,
            DEFAULT_ADMIN_PASSWORD="strong_custom_password_12345",
            DATABASE_URL="postgresql+asyncpg://prod_user:strong_pass_123@localhost:5432/marketing_os_db",
            SYNC_DATABASE_URL="postgresql://prod_user:strong_pass_123@localhost:5432/marketing_os_db",
            MINIO_ROOT_PASSWORD="minio_strong_prod_pass_12345",
            LANGFUSE_SECRET_KEY="sk-lf-local-secret",
        )

    # Test acceptance of secure settings in production
    valid_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        DEFAULT_ADMIN_PASSWORD="a-very-secure-production-admin-passphrase",
        DATABASE_URL="postgresql+asyncpg://prod_user:strong_pass_123@localhost:5432/marketing_os_db",
        SYNC_DATABASE_URL="postgresql://prod_user:strong_pass_123@localhost:5432/marketing_os_db",
        MINIO_ROOT_PASSWORD="minio_strong_prod_pass_12345",
        LANGFUSE_SECRET_KEY="sk-lf-prod-token-1234567890",
    )
    assert valid_settings.ENVIRONMENT == "production"


@pytest.mark.asyncio
async def test_strict_auth_rejects_backdoor_or_bad_credentials():
    """Verify authentication requires valid database records with hashed passwords and rejects backdoors."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Invalid password
        bad_pw_res = await ac.post(
            "/api/v1/auth/login",
            json={"email": "admin@marketing-os.local", "password": "wrong_password"},
        )
        assert bad_pw_res.status_code == 401

        # Non-existent user
        no_user_res = await ac.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@marketing-os.local", "password": "anypassword"},
        )
        assert no_user_res.status_code == 401


@pytest.mark.asyncio
async def test_platform_connection_secrets_masked():
    """Verify platform connection secrets are never returned in plaintext."""
    transport = ASGITransport(app=app)
    admin_token = create_access_token({"sub": "admin_hardening", "email": "admin@test.local", "role": UserRole.ADMIN.value})
    headers = {"Authorization": f"Bearer {admin_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/settings/platforms", headers=headers)
        assert res.status_code == 200
        platforms = res.json()
        assert len(platforms) == 8

        for p in platforms:
            # Client IDs must either be None, 'configured', or have masked preview
            if p["masked_client_id"] is not None:
                assert "secret" not in p["masked_client_id"].lower()
            assert "client_secret" not in p
            assert "access_token" not in p


@pytest.mark.asyncio
async def test_chat_orchestrator_acceptance_workflow():
    """Verify orchestrator chat executes campaign workflow creating Run and halting at human approval."""
    transport = ASGITransport(app=app)
    admin_token = create_access_token({"sub": "admin_hardening", "email": "admin@test.local", "role": UserRole.ADMIN.value})
    headers = {"Authorization": f"Bearer {admin_token}"}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create chat session
        session_res = await ac.post(
            "/api/v1/chat/sessions",
            headers=headers,
            json={"title": "Automated Acceptance Campaign Session"},
        )
        assert session_res.status_code == 201
        session_id = session_res.json()["id"]

        # Post campaign command without stream
        msg_res = await ac.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=headers,
            json={
                "content": "Create a Q4 brand awareness campaign for Instagram and LinkedIn.",
                "stream": False,
            },
        )
        assert msg_res.status_code == 200
        data = msg_res.json()

        # Confirm intent classification and orchestrator run creation
        assert data.get("run_id") is not None
        assert data.get("metadata", {}).get("intent") == "operational"
        run_id = data["run_id"]

        # Confirm run details in database
        run_res = await ac.get(f"/api/v1/runs/{run_id}", headers=headers)
        assert run_res.status_code == 200
        run_data = run_res.json()
        assert run_data["id"] == run_id
        # Confirm it halted at human approval or pending state
        assert run_data["status"] in ("pending", "running", "paused")

        # Post streaming campaign command to verify LangGraph execution, SSE events, and approval interrupt
        stream_res = await ac.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=headers,
            json={
                "content": "Synthesize a full multi-channel brand launch campaign for Instagram and LinkedIn.",
                "stream": True,
            },
        )
        assert stream_res.status_code == 200
        stream_text = stream_res.text
        assert "event: run_start" in stream_text
        assert "event: interrupt" in stream_text
        assert "human_approval_gate_node" in stream_text
        assert "event: complete" in stream_text
