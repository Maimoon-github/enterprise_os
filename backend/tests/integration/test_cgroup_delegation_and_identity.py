"""Integration and unit tests for native delegated cgroup-v2 management
and distinct OS user identity enforcement (SO_PEERCRED).
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import pytest

from app.integrations.sandbox.provisioner_daemon import (
    DelegatedCgroupManager,
    SocketIdentityPolicy,
)


def test_socket_identity_distinct_user_enforcement() -> None:
    """Prove SocketIdentityPolicy strictly enforces caller UID != daemon UID
    when require_distinct_user is active (production deployment mode)."""
    server_uid = os.getuid()
    different_uid = server_uid + 100
    backend_uid = 999
    backend_gid = 998

    # Local development mode: same UID allowed
    dev_policy = SocketIdentityPolicy(
        allowed_uids={backend_uid},
        allowed_gids={backend_gid},
        allow_same_user=True,
        require_distinct_user=False,
    )
    ok_dev, msg_dev = dev_policy.authorize(server_uid, 1000)
    assert ok_dev is True
    assert "local development mode" in msg_dev

    # Production boundary: same UID strictly rejected
    prod_policy = SocketIdentityPolicy(
        allowed_uids={backend_uid, different_uid},
        allowed_gids={backend_gid},
        allow_same_user=False,
        require_distinct_user=True,
    )
    ok_same, msg_same = prod_policy.authorize(server_uid, 1000)
    assert ok_same is False
    assert "requires distinct user identity" in msg_same

    # Distinct authorized peer UID accepted
    ok_diff, msg_diff = prod_policy.authorize(different_uid, 1000)
    assert ok_diff is True
    assert f"Authorized peer UID {different_uid}" in msg_diff

    # Distinct authorized peer GID accepted
    ok_gid, msg_gid = prod_policy.authorize(server_uid + 50, backend_gid)
    assert ok_gid is True
    assert f"Authorized peer GID {backend_gid}" in msg_gid

    # Root UID 0 accepted
    ok_root, _ = prod_policy.authorize(0, 0)
    assert ok_root is True


def test_delegated_cgroup_manager_full_lifecycle(tmp_path: Path) -> None:
    """Prove DelegatedCgroupManager moves daemon to leaf cgroup, enables subtree_control,
    creates per-attempt scopes with hardware limits, and scrubs them on teardown."""
    cgroup_root = tmp_path / "enterprise-os-provisioner.service"
    cgroup_root.mkdir(parents=True)

    # Mock host cgroup controllers
    (cgroup_root / "cgroup.controllers").write_text("cpu memory pids", encoding="utf-8")
    (cgroup_root / "cgroup.procs").write_text(f"{os.getpid()}\n", encoding="utf-8")

    # Stale attempt cgroup simulation from abnormal termination
    stale_attempt = cgroup_root / "sbx-stale-attempt-deadbeef"
    stale_attempt.mkdir()
    (stale_attempt / "cgroup.procs").write_text("", encoding="utf-8")

    # Initialize delegation manager
    manager = DelegatedCgroupManager(cgroup_root=cgroup_root)

    # 1. Assert manager is active
    assert manager.active is True
    assert manager.enabled_controllers == {"cpu", "memory", "pids"}

    # 2. Assert stale attempt cgroup was scrubbed during initialization
    assert not stale_attempt.exists()

    # 3. Assert daemon process was migrated to leaf cgroup
    assert (cgroup_root / "daemon").is_dir()
    assert (cgroup_root / "daemon" / "cgroup.procs").exists()
    assert str(os.getpid()) in (cgroup_root / "daemon" / "cgroup.procs").read_text()

    # 4. Assert cgroup.subtree_control has controllers enabled
    subtree_control = (cgroup_root / "cgroup.subtree_control").read_text().strip()
    assert "cpu" in subtree_control and "memory" in subtree_control and "pids" in subtree_control

    # 5. Create attempt scope
    with manager.create_attempt_scope(
        stage_attempt_id="att-test-01",
        execution_id="exec-test-9999",
        memory_mb=256,
        cpu_cores=1.5,
        pids_limit=64,
    ) as (attempt_dir, preexec_fn):
        assert attempt_dir is not None
        assert attempt_dir.exists()
        assert attempt_dir.name == "sbx-att-test-01-exec-tes"

        # Check resource ceiling files
        mem_max = (attempt_dir / "memory.max").read_text().strip()
        assert mem_max == str(256 * 1024 * 1024)

        pids_max = (attempt_dir / "pids.max").read_text().strip()
        assert pids_max == "64"

        cpu_max = (attempt_dir / "cpu.max").read_text().strip()
        assert cpu_max == "150000 100000"

        # Check preexec attach function writes PID
        assert callable(preexec_fn)
        preexec_fn()
        procs_text = (attempt_dir / "cgroup.procs").read_text()
        assert str(os.getpid()) in procs_text

        # Prepare for exit
        (attempt_dir / "cgroup.procs").write_text("", encoding="utf-8")

    # 6. Assert attempt scope was cleanly destroyed
    assert not attempt_dir.exists()


def test_delegated_cgroup_manager_fallback_when_unavailable(tmp_path: Path) -> None:
    """Prove DelegatedCgroupManager fails safe without error when delegation is unsupported."""
    empty_root = tmp_path / "non_cgroup_dir"
    empty_root.mkdir()

    manager = DelegatedCgroupManager(cgroup_root=empty_root)
    assert manager.active is False

    with manager.create_attempt_scope(
        stage_attempt_id="att-fallback",
        execution_id="exec-fallback",
        memory_mb=128,
        cpu_cores=1.0,
    ) as (attempt_dir, preexec_fn):
        assert attempt_dir is None
        assert preexec_fn is None
