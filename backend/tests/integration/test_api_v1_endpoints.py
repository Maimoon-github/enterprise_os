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
        assert len(schedules) >= 3
        schedule_names = {s["name"] for s in schedules}
        assert "ingest-social-metrics-every-6-hours" in schedule_names
        assert "midnight-brand-compliance-audit" in schedule_names
        assert "poll-due-schedules-every-5-minutes" in schedule_names
        assert "weekly-analytics-backup-sunday" in schedule_names

        # Test trigger
        trigger_res = await ac.post(
            "/api/v1/schedules/beat/midnight-brand-compliance-audit/trigger",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert trigger_res.status_code == 200
        trigger_data = trigger_res.json()
        assert trigger_data["schedule_name"] == "midnight-brand-compliance-audit"


@pytest.mark.asyncio
async def test_mcp_servers_api():
    """Verify GET /api/v1/mcp-servers and POST /api/v1/mcp-servers/{id}/sync."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = create_access_token({"sub": "admin_1", "email": "a@ex.com", "role": "admin"})
        headers = {"Authorization": f"Bearer {admin_token}"}

        res = await ac.get("/api/v1/mcp-servers", headers=headers)
        assert res.status_code == 200
        servers = res.json()
        assert len(servers) == 4
        names = {s["name"] for s in servers}
        assert "brand_rag_server" in names
        assert "social_gateway_server" in names
        assert "media_studio_server" in names
        assert "analytics_server" in names

        # Test sync discovery endpoint
        sync_res = await ac.post("/api/v1/mcp-servers/brand_rag_server/sync", headers=headers)
        assert sync_res.status_code == 200
        sync_data = sync_res.json()
        assert sync_data["status"] == "synced"
        assert sync_data["server_id"] == "brand_rag_server"
        assert sync_data["tools_synced"] >= 3


@pytest.mark.asyncio
async def test_media_and_analytics_endpoints():
    """Verify /api/v1/media presigned URL generation and /api/v1/analytics KPIs and anomalies."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = create_access_token({"sub": "admin_1", "email": "a@ex.com", "role": "admin"})
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Media presigned
        presigned_res = await ac.get("/api/v1/media/presigned?filename=hero_banner.png", headers=headers)
        assert presigned_res.status_code == 200
        presigned = presigned_res.json()
        assert "hero_banner.png" in presigned["key"]
        assert presigned["bucket"] is not None
        assert presigned["url"] is not None

        # Media list
        media_list = await ac.get("/api/v1/media", headers=headers)
        assert media_list.status_code == 200
        assert isinstance(media_list.json(), list)

        # Post real analytics event
        brand_list = await ac.get("/api/v1/brands", headers=headers)
        brand_id = brand_list.json()[0]["id"]
        post_res = await ac.post(
            "/api/v1/analytics/events",
            headers=headers,
            json={
                "brand_id": brand_id,
                "platform": "linkedin",
                "external_post_id": "post_test_1",
                "metric_type": "impressions",
                "metric_value": 1500,
            },
        )
        assert post_res.status_code == 201

        # Analytics KPIs
        kpi_res = await ac.get("/api/v1/analytics/kpis", headers=headers)
        assert kpi_res.status_code == 200
        kpis = kpi_res.json()
        assert kpis["impressions_total"] >= 1500
        assert kpis["platforms_active"] >= 1

        # Analytics Anomalies
        anom_res = await ac.get("/api/v1/analytics/anomalies", headers=headers)
        assert anom_res.status_code == 200
        anomalies = anom_res.json()
        assert isinstance(anomalies, list)

        # Analytics Overview
        overview_res = await ac.get("/api/v1/analytics/overview", headers=headers)
        assert overview_res.status_code == 200
        overview = overview_res.json()
        assert "kpis" in overview
        assert "outliers" in overview
        assert "proposals" in overview


@pytest.mark.asyncio
async def test_skills_api_lifecycle():
    """Verify GET /api/v1/skills, GET /api/v1/skills/{name}, and POST /api/v1/skills/validate."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = create_access_token({"sub": "admin_1", "email": "a@ex.com", "role": "admin"})
        headers = {"Authorization": f"Bearer {admin_token}"}

        # List skills
        res = await ac.get("/api/v1/skills", headers=headers)
        assert res.status_code == 200
        skills = res.json()
        assert len(skills) >= 4
        names = {s["name"] for s in skills}
        assert "brand-voice-audit" in names
        assert "multi-platform-copy" in names
        assert "competitor-recon" in names
        assert "media-compliance" in names

        # Get skill detail
        detail_res = await ac.get("/api/v1/skills/brand-voice-audit", headers=headers)
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["name"] == "brand-voice-audit"
        assert "Brand Voice Audit Skill" in detail["tier2_body"]
        assert "scripts/check_tone.py" in detail["tier3_resources"]

        # Validate valid skill
        val_payload = {
            "name": "custom-audit-skill",
            "content": "---\nname: custom-audit-skill\ndescription: Custom audit playbook. Activate when testing.\nallowed-tools: none\n---\n\n# Custom Audit\nInstructions",
        }
        val_res = await ac.post("/api/v1/skills/validate", json=val_payload, headers=headers)
        assert val_res.status_code == 200
        val_data = val_res.json()
        assert val_data["valid"] is True
        assert len(val_data["errors"]) == 0

        # Validate invalid skill (missing delimiter, name mismatch)
        invalid_payload = {
            "name": "custom-audit-skill",
            "content": "Not YAML frontmatter",
        }
        inv_res = await ac.post("/api/v1/skills/validate", json=invalid_payload, headers=headers)
        assert inv_res.status_code == 200
        inv_data = inv_res.json()
        assert inv_data["valid"] is False
        assert len(inv_data["errors"]) > 0


@pytest.mark.asyncio
async def test_observability_endpoints():
    """Verify OpenTelemetry and Langfuse observability traces, stats, evaluations, and golden suite run."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_token = create_access_token({"sub": "admin_1", "email": "a@ex.com", "role": "admin"})
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Traces
        traces_res = await ac.get("/api/v1/observability/traces", headers=headers)
        assert traces_res.status_code == 200
        traces_data = traces_res.json()
        assert traces_data["openinference_conventions"] == "enabled"
        assert "Langfuse" in traces_data["exporter"]

        # Stats
        stats_res = await ac.get("/api/v1/observability/stats", headers=headers)
        assert stats_res.status_code == 200
        stats_data = stats_res.json()
        assert "trajectory_gate_pass_rate" in stats_data
        assert "brand_voice_rubric_avg" in stats_data
        assert stats_data["token_velocity_per_min"] > 0

        # Run golden regression suite
        run_res = await ac.post("/api/v1/observability/evaluations/run", headers=headers)
        assert run_res.status_code == 200
        run_data = run_res.json()
        assert run_data["total_scenarios"] == 3
        assert run_data["passed"] >= 2
        assert len(run_data["results"]) == 3

        # List recorded evaluations
        evals_res = await ac.get("/api/v1/observability/evaluations", headers=headers)
        assert evals_res.status_code == 200
        evals_data = evals_res.json()
        assert evals_data["total"] >= 1
        assert len(evals_data["evaluations"]) >= 1
        kinds = {e["annotator_kind"] for e in evals_data["evaluations"]}
        assert "CODE" in kinds or "LLM" in kinds



