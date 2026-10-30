import pytest
from app.core.security import create_access_token
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_and_ready():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

        res = await ac.get("/ready")
        assert res.status_code == 200
        assert res.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_auth_login_and_refresh():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_res = await ac.post(
            "/api/v1/auth/login",
            json={"email": "admin@marketing-os.local", "password": "admin123"},
        )
        assert login_res.status_code == 200
        data = login_res.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "admin"

        # Test refresh
        refresh_res = await ac.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": data["refresh_token"]},
        )
        assert refresh_res.status_code == 200
        refreshed = refresh_res.json()
        assert "access_token" in refreshed


@pytest.mark.asyncio
async def test_unauthorized_access_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/brands")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_rbac_protection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Viewer token trying to access admin endpoint
        viewer_token = create_access_token({"sub": "viewer_1", "email": "v@ex.com", "role": "viewer"})
        res = await ac.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert res.status_code == 403

        # Admin token can access
        admin_token = create_access_token({"sub": "admin_1", "email": "a@ex.com", "role": "admin"})
        res = await ac.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_settings_sandbox_and_celery_metadata():
    """Verify GET /api/v1/settings returns Podman sandbox limits and Celery queue configurations."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = create_access_token({"sub": "admin_1", "email": "a@ex.com", "role": "admin"})
        res = await ac.get(
            "/api/v1/settings",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["sandbox_engine"] == "rootless-podman"
        assert "sandbox_limits" in data
        assert data["sandbox_limits"]["memory_limit"] == "512m"
        assert data["sandbox_limits"]["cpu_limit"] == "1.0"
        assert data["sandbox_limits"]["network_default"] == "none"
        assert "celery_queues" in data
        assert "orchestrator_queue" in data["celery_queues"]
        assert "publishing_queue" in data["celery_queues"]
        assert data["beat_schedules_count"] >= 3


@pytest.mark.asyncio
async def test_schedules_beat_endpoints():
    """Verify Celery Beat periodic schedules endpoint and manual dispatch trigger."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = create_access_token({"sub": "admin_1", "email": "a@ex.com", "role": "admin"})
        res = await ac.get(
            "/api/v1/schedules/beat",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        schedules = res.json()
        assert len(schedules) == 3
        schedule_names = {s["name"] for s in schedules}
        assert "ingest-social-metrics-every-6-hours" in schedule_names
        assert "midnight-brand-compliance-audit" in schedule_names
        assert "poll-due-schedules-every-5-minutes" in schedule_names

        # Test trigger
        trigger_res = await ac.post(
            "/api/v1/schedules/beat/midnight-brand-compliance-audit/trigger",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert trigger_res.status_code == 200
        trigger_data = trigger_res.json()
        assert trigger_data["schedule_name"] == "midnight-brand-compliance-audit"
