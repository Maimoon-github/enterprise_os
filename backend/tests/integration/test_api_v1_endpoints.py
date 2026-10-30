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
