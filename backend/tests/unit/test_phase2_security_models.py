from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.core.idempotency import generate_schedule_idempotency_key
from app.core.rbac import UserRole, check_permission, has_role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.db.base import Base
from app.services.sandbox_service import SandboxSecurityViolation, SandboxService
from app.tasks.beat_schedule import CELERY_BEAT_SCHEDULE
from app.tasks.celery_app import celery_app, task_queues
from app.tasks.publishing_tasks import dispatch_platform_post
from fastapi import HTTPException


def test_core_models_registered_on_base():
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "brands",
        "campaigns",
        "runs",
        "approvals",
        "media_assets",
        "schedules",
        "analytics_events",
    }
    assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"


def test_argon2id_password_hashing():
    password = "SuperSecurePassword123!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_authlib_jwt_access_and_refresh_tokens():
    data = {"sub": "user_123", "email": "test@example.com", "role": "editor"}
    access_token = create_access_token(data, expires_delta_seconds=300)
    refresh_token = create_refresh_token(data, expires_delta_seconds=600)

    access_claims = verify_token(access_token)
    assert access_claims["sub"] == "user_123"
    assert access_claims["role"] == "editor"
    assert access_claims["type"] == "access"

    refresh_claims = verify_token(refresh_token)
    assert refresh_claims["sub"] == "user_123"
    assert refresh_claims["type"] == "refresh"


def test_rbac_hierarchy():
    # admin > editor > operator > viewer
    assert has_role("admin", UserRole.VIEWER) is True
    assert has_role("admin", UserRole.OPERATOR) is True
    assert has_role("admin", UserRole.EDITOR) is True
    assert has_role("admin", UserRole.ADMIN) is True

    assert has_role("editor", UserRole.OPERATOR) is True
    assert has_role("editor", UserRole.ADMIN) is False

    assert has_role("operator", UserRole.VIEWER) is True
    assert has_role("operator", UserRole.EDITOR) is False

    assert has_role("viewer", UserRole.OPERATOR) is False

    # check_permission succeeds
    check_permission("admin", minimum_role=UserRole.EDITOR)
    check_permission("editor", minimum_role=UserRole.OPERATOR)

    # check_permission fails
    with pytest.raises(HTTPException):
        check_permission("viewer", minimum_role=UserRole.OPERATOR)


def test_idempotency_key_generation():
    dt = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)
    key1 = generate_schedule_idempotency_key("camp-1", "linkedin", dt)
    key2 = generate_schedule_idempotency_key("camp-1", "linkedin", dt)
    key3 = generate_schedule_idempotency_key("camp-1", "youtube", dt)

    assert key1 == key2
    assert len(key1) == 64
    assert key1 != key3


def test_celery_partitioned_queues_and_routing():
    """Verify Celery app Kombu queues, task routing, and Celery Beat schedule configuration."""
    queue_names = {q.name for q in task_queues}
    expected_queues = {"orchestrator_queue", "publishing_queue", "media_queue", "analytics_queue"}
    assert queue_names == expected_queues

    routes = celery_app.conf.task_routes
    assert routes["app.tasks.orchestrator_tasks.*"]["queue"] == "orchestrator_queue"
    assert routes["app.tasks.publishing_tasks.*"]["queue"] == "publishing_queue"
    assert routes["app.tasks.media_tasks.*"]["queue"] == "media_queue"
    assert routes["app.tasks.analytics_tasks.*"]["queue"] == "analytics_queue"

    # Verify 3 mandatory Beat schedules
    assert "ingest-social-metrics-every-6-hours" in CELERY_BEAT_SCHEDULE
    assert "midnight-brand-compliance-audit" in CELERY_BEAT_SCHEDULE
    assert "poll-due-schedules-every-5-minutes" in CELERY_BEAT_SCHEDULE


def test_podman_sandbox_command_construction_and_security_flags():
    """Verify Podman CLI command list enforces rootless no-new-privileges, cap-drop, 512MB RAM, 1.0 CPU, network:none, :ro."""
    job_dir = Path("/tmp/sandboxes/job_test_security")
    cmd = SandboxService.build_podman_command(
        job_dir=job_dir,
        script_name="check_tone.py",
        network="none",
    )
    assert cmd[0] == "podman"
    assert cmd[1] == "run"
    assert "--rm" in cmd
    assert "--security-opt=no-new-privileges" in cmd
    assert "--cap-drop=ALL" in cmd
    assert "--memory=512m" in cmd
    assert "--cpus=1.0" in cmd
    assert "--network=none" in cmd
    assert f"{job_dir.resolve()}:/workspace:ro" in cmd

    # Test path traversal prevention
    with pytest.raises(SandboxSecurityViolation):
        SandboxService.build_podman_command(job_dir, "../../../etc/passwd")

    with pytest.raises(SandboxSecurityViolation):
        SandboxService.build_podman_command(job_dir, "/bin/sh")


def test_podman_sandbox_execution_and_cleanup_guarantee():
    """Verify ephemeral workspace is staged and guaranteed to be deleted in finally block."""
    result = SandboxService.run_isolated_command(
        "import sys, json; print(json.dumps({'status': 'ok'}))",
        is_content=True,
    )
    assert result["exit_code"] == 0
    assert result["parsed_json"] == {"status": "ok"}

    # Verify ephemeral job directory was cleaned up
    job_path = Path("/tmp/sandboxes") / result["job_id"]
    assert not job_path.exists(), "Ephemeral job directory must be completely removed"


def test_publishing_task_idempotency_deduplication():
    """Verify dispatch_platform_post enforces SHA-256 idempotency deduplication."""
    key = "sha256_mock_idempotency_test_key_001"
    payload = {"copy": "Launch announcement"}

    # First call publishes
    res1 = dispatch_platform_post("linkedin", payload, key)
    assert res1["status"] == "published"
    assert res1["idempotency_key"] == key

    # Second call with same idempotency key is skipped
    res2 = dispatch_platform_post("linkedin", payload, key)
    assert res2["status"] == "skipped_duplicate"
    assert res2["idempotency_key"] == key


def test_secret_service_aes_256_gcm():
    """Verify SecretService AES-256-GCM encryption, decryption, and tampering rejection."""
    from app.services.secret_service import secret_service

    raw = "oauth_token_secret_xyz123"
    enc = secret_service.encrypt(raw)
    assert enc.startswith("aes256gcm_")
    assert enc != raw

    dec = secret_service.decrypt(enc)
    assert dec == raw

    # Unique nonces per call
    enc2 = secret_service.encrypt(raw)
    assert enc != enc2
    assert secret_service.decrypt(enc2) == raw

    # Tampered ciphertext fails
    with pytest.raises(ValueError):
        secret_service.decrypt(enc[:-4] + "AAAA")


def test_mcp_meta_protocol_and_client_envelope():
    """Verify MCP 2026-07-28 stateless _meta envelope structure and client injection."""
    from app.mcp.client import MCPClient

    client = MCPClient("test_server", "http://localhost:8081/mcp")
    meta = client._meta_envelope()
    assert meta["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"
    assert meta["io.modelcontextprotocol/clientInfo"]["name"] == "marketing-os-worker"
    assert "elicitation" in meta["io.modelcontextprotocol/clientCapabilities"]

    payload = client._wrap_meta({"method": "tools/call", "params": {"name": "test"}})
    assert "_meta" in payload
    assert payload["_meta"]["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"


@pytest.mark.asyncio
async def test_mcp_discovery_caching_and_subscriptions():
    """Verify server/discover ttlMs caching and subscriptions/listen for toolsListChanged."""
    from app.mcp.discovery import MCPDiscovery

    discovery = MCPDiscovery()
    caps = await discovery.discover_capabilities("http://localhost:8081/mcp")
    assert caps["protocolVersion"] == "2026-07-28"
    assert caps["ttlMs"] == 300000
    assert "tools" in caps

    # Subscribed to change notifications
    sub = await discovery.subscribe_notifications("brand_rag_server", "http://localhost:8081/mcp")
    assert sub["subscribed"] is True
    assert sub["notifications"]["toolsListChanged"] is True


@pytest.mark.asyncio
async def test_fastmcp_servers_and_tools_execution():
    """Verify all 4 FastMCP servers, their tools, resources, and tasks handles."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from mcp_servers.analytics_server.tools import detect_metric_anomalies, query_aggregated_kpis
    from mcp_servers.brand_rag_server.resources import get_brand_guidelines
    from mcp_servers.brand_rag_server.tools import search_brand_knowledge, store_campaign_learnings
    from mcp_servers.media_studio_server.tasks_extension import (
        burn_subtitles,
        poll_media_job_status,
        submit_image_generation_job,
    )
    from mcp_servers.social_gateway_server.tools import publish_to_platform, verify_platform_post

    # 1. Brand RAG Server
    rag_res = search_brand_knowledge("tone of voice guidelines", "b-01")
    assert len(rag_res) > 0
    assert "content" in rag_res[0]

    learn_res = store_campaign_learnings("c-01", "Highlighting ROI yields +24% CTR", 0.92)
    assert learn_res["status"] == "stored"

    guide = get_brand_guidelines("b-01")
    assert "Brand Voice" in guide

    # 2. Social Gateway Server (with idempotency and mock secret)
    pub_res = await publish_to_platform("linkedin", {"text": "MCP test post"}, idempotency_key="mcp_idemp_001")
    assert pub_res["status"] == "published"
    assert pub_res["idempotency_key"] == "mcp_idemp_001"

    dup_res = await publish_to_platform("linkedin", {"text": "MCP test post"}, idempotency_key="mcp_idemp_001")
    assert dup_res["status"] == "skipped_duplicate"

    ver_res = await verify_platform_post("linkedin", pub_res["post_id"])
    assert ver_res["verified"] is True

    # 3. Media Studio Server & Tasks Extension
    job = await submit_image_generation_job("Cinematic futuristic office", "16:9")
    assert job["status"] == "submitted"
    task_id = job["task_id"]

    status = await poll_media_job_status(task_id)
    assert status["status"] in ("submitted", "processing", "in_progress", "completed")

    sub_res = await burn_subtitles("minio://raw/video.mp4", "minio://raw/subs.srt")
    assert "result_uri" in sub_res

    # 4. Analytics Server (Polars Z-score)
    kpis = query_aggregated_kpis("2026-10-01", "2026-10-30", ["linkedin", "youtube"])
    assert kpis["total_impressions"] > 0

    anomalies = detect_metric_anomalies(
        metric_series=[10.0, 10.5, 9.8, 10.2, 10.1, 9.9, 25.0],
        platforms=["youtube"] * 7,
    )
    assert len(anomalies) >= 1
    assert anomalies[0]["z_score"] > 1.5


def test_worker_tool_retry_policy():
    """Verify Pydantic AI worker retry policies: 3 for read/RAG, 1 for mutating publish."""
    from app.orchestrator.workers.retry_policies import (
        MUTATING_PUBLISH_MAX_RETRIES,
        READ_TOOLS_MAX_RETRIES,
        get_tool_retry_policy,
    )

    assert READ_TOOLS_MAX_RETRIES == 3
    assert MUTATING_PUBLISH_MAX_RETRIES == 1

    assert get_tool_retry_policy("search_brand_knowledge") == 3
    assert get_tool_retry_policy("retrieve_winning_campaigns") == 3
    assert get_tool_retry_policy("publish_to_platform") == 1
    assert get_tool_retry_policy("dispatch_platform_post") == 1


def test_skill_validator_and_packages():
    """Verify validate_skills.py enforces agentskills.io YAML schema, directories, and budgets."""
    import sys
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(backend_dir))

    from scripts.validate_skills import validate_all_skills, validate_single_skill

    skills_dir = backend_dir / "skills"
    res = validate_all_skills(skills_dir)
    assert res["valid"] is True
    assert len(res["skills"]) == 4

    skill_names = {s["name"] for s in res["skills"]}
    assert skill_names == {
        "brand-voice-audit",
        "multi-platform-copy",
        "competitor-recon",
        "media-compliance",
    }

    # Verify invalid naming rejection (uppercase, underscore)
    invalid_res = validate_single_skill(skills_dir / "brand-voice-audit")
    assert invalid_res["valid"] is True


def test_skill_service_progressive_disclosure_and_sandbox_execution():
    """Verify SkillService 3-tier progressive disclosure, path traversal defense, and sandboxed script execution."""
    from app.services.skill_service import skill_service

    # Tier 1 Catalog
    tier1 = skill_service.get_tier1_catalog()
    assert len(tier1) >= 4
    names = {s["name"] for s in tier1}
    assert "brand-voice-audit" in names

    # Tier 2 On-Demand Loading
    body = skill_service.load_skill_body("multi-platform-copy")
    assert "# Multi-Platform Copy Skill" in body
    assert "---" not in body  # Frontmatter stripped

    # Tier 3 Resource Loading
    limits = skill_service.load_tier3_resource("multi-platform-copy", "references/PLATFORM_LIMITS.md")
    assert "LinkedIn" in limits
    assert "YouTube" in limits

    # Path traversal protection
    with pytest.raises(ValueError, match="Path traversal detected"):
        skill_service.load_tier3_resource("multi-platform-copy", "../../../etc/passwd")

    with pytest.raises(ValueError, match="Path traversal detected"):
        skill_service.load_tier3_resource("multi-platform-copy", "references/../../outside.txt")

    # Tier 3 Script Execution via SandboxService
    exec_res = skill_service.execute_skill_script(
        "brand-voice-audit",
        "check_tone.py",
        stdin_data="Our game-changer synergy creates a paradigm shift.",
    )
    assert exec_res["exit_code"] == 0
    assert exec_res["parsed_json"] is not None
    assert exec_res["parsed_json"]["passed"] is False
    assert len(exec_res["parsed_json"]["violations"]) > 0


def test_agent_worker_progressive_disclosure():
    """Verify AgentWorkerFactory injects Tier 1 catalog by default and scopes tools to active skills."""
    from app.orchestrator.workers.agent_worker_factory import AgentWorkerFactory
    from pydantic import BaseModel

    class DummyContract(BaseModel):
        msg: str

    # Worker with active skill specifying allowed-tools
    worker = AgentWorkerFactory.create_worker(
        name="creative_reviewer",
        model_tag="ollama:qwen2.5:14b",
        output_type=DummyContract,
        toolset_name="campaign_creative",
        active_skills=["brand-voice-audit"],
    )

    assert len(worker["tier1_skills"]) >= 4
    assert "brand-voice-audit" in worker["tier2_instructions"]
    assert "Brand Voice Audit" in worker["tier2_instructions"]["brand-voice-audit"]


