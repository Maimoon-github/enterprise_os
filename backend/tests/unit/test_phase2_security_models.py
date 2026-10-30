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
