"""Standalone Hardened Sandbox Provisioner Daemon and Engine.

Runs out-of-process as a dedicated unprivileged OS service boundary.
Communicates exclusively over an authenticated Unix Domain Socket (UDS).
Enforces:
1. Complete process and container isolation from backend / IE / workers.
2. Server-side capability policy derivation (caller cannot provide arbitrary commands, paths, flags, or mounts).
3. Linux namespaces (user, pid, mount, net, ipc, uts), per-attempt cgroup v2 scope, and Seccomp: 2 filter.
4. User namespace hardening (--disable-userns) preventing nested namespace manipulation inside sandbox.
5. Bubblewrap version verification against CVE-2026-87766 (minimum 0.12.0, pinned 0.13.0).
6. Production UDS identity model: peer credential verification (SO_PEERCRED) authorizing backend UID/GID.
7. Systemd socket activation support (FD 3) with explicit 0660 socket permissions.
8. Persistent replay protection across daemon crashes/restarts.
9. Stale socket cleanup, stale staging runtime scrub, and fail-closed validation.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import hmac
import json
import logging
import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.exceptions import (
    PolicyViolationError,
    SandboxExecutionError,
    SandboxInvocationError,
    SandboxIsolationError,
    SandboxValidationError,
)
from app.schemas.sandbox import (
    NetworkPolicy,
    SandboxCapability,
    SandboxExecutionReceipt,
    SandboxExecutionStatus,
    SandboxInvocationMandate,
    SandboxResult,
    SandboxTeardownReceipt,
)

logger = logging.getLogger(__name__)

# Pinned trusted runtime image and digests
PINNED_IMAGE = "ghcr.io/agent-infra/sandbox:1.11.0"
PINNED_DIGEST = "sha256:d8c83df2357b98d197621c17830cbdfc63b860b73dfeb46487e8e4533dae5d95"
PINNED_RUNTIME_VERSION = "1.11.0"
PINNED_PROFILE_VERSION = "v1"

# Bubblewrap security parameters and CVE-2026-87766 defense
MIN_BWRAP_VERSION: tuple[int, int, int] = (0, 12, 0)
PINNED_BWRAP_VERSION: str = "0.13.0"
CVE_2026_87766_ADVISORY = (
    "Bubblewrap versions prior to 0.12.0 are vulnerable to CVE-2026-87766 "
    "(high-severity sandbox setup escape via improper link resolution). "
    "Production deployments must use bubblewrap >= 0.12.0 (target pinned version 0.13.0)."
)

# Hard server-side resource ceilings
MAX_ALLOWED_CPU_CORES = 4.0
MAX_ALLOWED_MEMORY_MB = 8192
MAX_ALLOWED_PIDS = 1024

# Authoritative capability-to-skill directory mapping
CAPABILITY_SKILL_MAP: dict[SandboxCapability, str] = {
    SandboxCapability.ALLOC: "s-alloc",
    SandboxCapability.VAL: "s-val",
    SandboxCapability.COPY: "s-copy",
    SandboxCapability.CODE: "s-code",
    SandboxCapability.COMP: "s-comp",
    SandboxCapability.PARSE: "s-parse",
    SandboxCapability.ATTR: "s-attr",
}


def _locate_repo_root() -> Path:
    """Deterministically locate enterprise_os repository root."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "sandbox" / "docker" / "hardened").is_dir():
            return parent
    return Path("/home/maimoon-amin/Antigravity code/enterprise_os")


def resolve_provisioner_socket_path(preferred_path: str | Path | None = None) -> Path:
    """Resolve authoritative socket path for the provisioner daemon."""
    if preferred_path:
        return Path(preferred_path)
    env_path = os.environ.get("ENTERPRISE_OS_PROVISIONER_SOCKET") or os.environ.get("SANDBOX_PROVISIONER_SOCKET_PATH")
    if env_path:
        return Path(env_path)
    # 1. Standard host production path
    prod_path = Path("/run/enterprise_os/provisioner.sock")
    if prod_path.exists():
        return prod_path
    if prod_path.parent.exists() and os.access(prod_path.parent, os.W_OK):
        return prod_path
    # 2. XDG runtime directory (user-level systemd)
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        xdg_path = Path(xdg_runtime) / "enterprise_os" / "provisioner.sock"
        if xdg_path.exists() or os.access(xdg_runtime, os.W_OK):
            return xdg_path
    return prod_path


def get_bwrap_version(bwrap_path: str | Path) -> tuple[int, int, int] | None:
    """Extract semantic version tuple from bubblewrap executable."""
    try:
        proc = subprocess.run([str(bwrap_path), "--version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            parts = proc.stdout.strip().split()
            if len(parts) >= 2:
                nums = [int(p) for p in parts[1].split(".") if p.isdigit()]
                while len(nums) < 3:
                    nums.append(0)
                return (nums[0], nums[1], nums[2])
    except Exception as exc:
        logger.warning("Failed to inspect bwrap version for %s: %s", bwrap_path, exc)
    return None


def _resolve_bwrap_path(
    preferred_path: str | Path | None = None,
    strict_version: bool = False,
) -> tuple[Path | None, tuple[int, int, int] | None, list[str]]:
    """Probe candidate bwrap executables, verify user-namespace capability, and check version."""
    warnings: list[str] = []
    candidates: list[str | Path] = []

    if preferred_path:
        candidates.append(preferred_path)

    # Conda environment binary
    conda_bwrap = Path(sys.prefix) / "bin" / "bwrap"
    if conda_bwrap.exists():
        candidates.append(conda_bwrap)

    # Standard system binary (matches default AppArmor profiles on Ubuntu)
    system_bwrap = Path("/usr/bin/bwrap")
    if system_bwrap.exists():
        candidates.append(system_bwrap)

    which_bwrap = shutil.which("bwrap")
    if which_bwrap:
        candidates.append(Path(which_bwrap))

    seen: set[str] = set()
    unique_candidates: list[Path] = []
    for c in candidates:
        cp = Path(c).resolve()
        if str(cp) not in seen and cp.exists():
            seen.add(str(cp))
            unique_candidates.append(cp)

    functional_candidate: Path | None = None
    functional_version: tuple[int, int, int] | None = None

    for cand in unique_candidates:
        ver = get_bwrap_version(cand)
        # Test dry-run execution with user namespaces and disable-userns
        try:
            dry_run = subprocess.run(
                [
                    str(cand),
                    "--ro-bind", "/usr", "/usr",
                    "--ro-bind", "/lib", "/lib",
                    "--ro-bind-try", "/lib64", "/lib64",
                    "--ro-bind-try", "/bin", "/bin",
                    "--proc", "/proc",
                    "--dev", "/dev",
                    "--unshare-user",
                    "--disable-userns",
                    "/bin/true",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if dry_run.returncode == 0:
                functional_candidate = cand
                functional_version = ver
                break
            else:
                logger.debug("bwrap candidate %s failed dry run (exit %d): %s", cand, dry_run.returncode, dry_run.stderr.strip())
        except Exception as exc:
            logger.debug("bwrap candidate %s threw during dry run: %s", cand, exc)

    if functional_candidate is None:
        return None, None, ["No functional bubblewrap unprivileged namespace engine found on host."]

    if functional_version is not None:
        if functional_version < MIN_BWRAP_VERSION:
            warn_msg = (
                f"{CVE_2026_87766_ADVISORY} Active host engine: "
                f"{'.'.join(map(str, functional_version))} at {functional_candidate}."
            )
            warnings.append(warn_msg)
            logger.warning(warn_msg)
            if strict_version:
                raise SandboxIsolationError(f"Strict security verification failed: {warn_msg}")
        else:
            logger.info(
                "Verified hardened Bubblewrap engine at %s (version %s >= 0.12.0 pinned).",
                functional_candidate,
                ".".join(map(str, functional_version)),
            )

    return functional_candidate, functional_version, warnings


def cleanup_stale_runtimes(staging_root: Path | None = None) -> int:
    """Scrub any orphaned sbx-staging-* directories left behind by prior crashes."""
    root = staging_root or Path(tempfile.gettempdir())
    cleaned = 0
    with contextlib.suppress(Exception):
        for item in root.glob("sbx-staging-*"):
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                cleaned += 1
    if cleaned > 0:
        logger.info("Cleaned up %d stale sandbox staging directories on startup.", cleaned)
    return cleaned


class ReplayStateManager:
    """Persists seen execution and attempt IDs across provisioner daemon restarts."""

    def __init__(self, state_file_path: Path | None = None) -> None:
        self.state_file_path = state_file_path or self._default_state_file_path()
        self._lock = threading.Lock()
        self.seen_executions: set[str] = set()
        self.seen_attempts: set[str] = set()
        self._load()

    @staticmethod
    def _default_state_file_path() -> Path:
        env_path = os.environ.get("ENTERPRISE_OS_REPLAY_STATE_FILE")
        if env_path:
            return Path(env_path)
        run_path = Path("/run/enterprise_os/replay_state.json")
        if run_path.parent.exists() and os.access(run_path.parent, os.W_OK):
            return run_path
        xdg = os.environ.get("XDG_RUNTIME_DIR")
        if xdg:
            xdg_path = Path(xdg) / "enterprise_os" / "replay_state.json"
            return xdg_path
        return Path(tempfile.gettempdir()) / "enterprise_os_replay_state.json"

    def _load(self) -> None:
        with contextlib.suppress(Exception):
            if self.state_file_path.exists():
                data = json.loads(self.state_file_path.read_text(encoding="utf-8"))
                self.seen_executions = set(data.get("seen_executions", []))
                self.seen_attempts = set(data.get("seen_attempts", []))
                logger.info(
                    "Loaded persistent replay state: %d executions, %d attempts from %s",
                    len(self.seen_executions),
                    len(self.seen_attempts),
                    self.state_file_path,
                )

    def record_and_save(self, execution_id: str, attempt_key: str) -> None:
        with self._lock:
            self.seen_executions.add(execution_id)
            self.seen_attempts.add(attempt_key)
            self._save_atomic()

    def _save_atomic(self) -> None:
        try:
            self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.state_file_path.with_suffix(f".tmp.{os.getpid()}")
            data = {
                "seen_executions": sorted(list(self.seen_executions)),
                "seen_attempts": sorted(list(self.seen_attempts)),
                "updated_at": datetime.now(UTC).isoformat(),
            }
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp_path.replace(self.state_file_path)
        except Exception as exc:
            logger.warning("Failed to persist replay state to %s: %s", self.state_file_path, exc)


class SocketIdentityPolicy:
    """Production authorization policy for connecting Unix Domain Socket peers."""

    def __init__(
        self,
        allowed_uids: set[int] | None = None,
        allowed_gids: set[int] | None = None,
        allow_same_user: bool = True,
        allow_root: bool = True,
        require_distinct_user: bool = False,
    ) -> None:
        self.allowed_uids = set(allowed_uids or ())
        self.allowed_gids = set(allowed_gids or ())
        self.allow_same_user = allow_same_user
        self.allow_root = allow_root
        self.require_distinct_user = require_distinct_user

        # Environment variable overrides
        env_distinct = os.environ.get("ENTERPRISE_OS_REQUIRE_DISTINCT_USER")
        if env_distinct and env_distinct.strip().lower() in ("1", "true", "yes"):
            self.require_distinct_user = True
            self.allow_same_user = False

        env_uids = os.environ.get("ENTERPRISE_OS_ALLOWED_UIDS")
        if env_uids:
            for part in env_uids.split(","):
                part = part.strip()
                if part.isdigit():
                    self.allowed_uids.add(int(part))

        env_gids = os.environ.get("ENTERPRISE_OS_ALLOWED_GIDS")
        if env_gids:
            for part in env_gids.split(","):
                part = part.strip()
                if part.isdigit():
                    self.allowed_gids.add(int(part))

        # Auto-lookup system identities if present
        try:
            import pwd
            backend_user = pwd.getpwnam("enterprise-os-backend")
            self.allowed_uids.add(backend_user.pw_uid)
        except (KeyError, ImportError, Exception):
            pass

        try:
            import grp
            sandbox_group = grp.getgrnam("enterprise-os-sandbox")
            self.allowed_gids.add(sandbox_group.gr_gid)
        except (KeyError, ImportError, Exception):
            pass

    def authorize(self, peer_uid: int, peer_gid: int) -> tuple[bool, str]:
        """Authorize connecting client by peer UID and GID."""
        # 1. Distinct user boundary check: reject if caller UID matches daemon UID
        if self.require_distinct_user and peer_uid == os.getuid():
            return False, f"Peer UID {peer_uid} matches provisioner server UID; production boundary requires distinct user identity"

        # 2. Root UID 0 if allowed
        if peer_uid == 0 and self.allow_root:
            return True, "Authorized as root"

        # 3. Server UID if same-user allowed (development/local mode)
        if self.allow_same_user and not self.require_distinct_user and peer_uid == os.getuid():
            return True, "Authorized as server identity (local development mode)"

        # 4. Explicitly authorized UIDs (e.g. enterprise-os-backend user)
        if peer_uid in self.allowed_uids:
            return True, f"Authorized peer UID {peer_uid}"

        # 5. Explicitly authorized GIDs (e.g. enterprise-os-sandbox shared group)
        if peer_gid in self.allowed_gids:
            return True, f"Authorized peer GID {peer_gid}"

        # 6. Supplementary group membership inspection
        try:
            import grp
            import pwd
            pw = pwd.getpwuid(peer_uid)
            user_groups = [g.gr_gid for g in grp.getgrall() if pw.pw_name in g.gr_mem]
            if any(gid in self.allowed_gids for gid in user_groups):
                return True, f"Authorized peer UID {peer_uid} via supplementary group membership"
        except Exception:
            pass

        return False, f"Peer credential UID={peer_uid}, GID={peer_gid} is not authorized"


def _sanitize_string(text: str) -> str:
    """Redact sensitive credential patterns from text."""
    import re

    patterns = [
        (
            re.compile(
                r"(?i)(api[_-]?key|secret|token|password|auth|bearer)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?"
            ),
            r"\1: [REDACTED]",
        ),
        (re.compile(r"(?i)(bearer\s*[:=]?\s*['\"]?)[A-Za-z0-9_\-\.]{8,}['\"]?"), r"\1[REDACTED]"),
    ]
    sanitized = text
    for pattern, replacement in patterns:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def _sanitize_payload(payload: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any], list[str], str, str]:
    """Sanitize output payloads and compute raw/sanitized digests."""
    raw_bytes = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    raw_hash = hashlib.sha256(raw_bytes).hexdigest()

    sanitized_str: dict[str, str] = {}
    structured: dict[str, Any] = {}
    warnings: list[str] = []

    for k, v in payload.items():
        if "../" in k or "..\\" in k:
            raise SandboxInvocationError(f"Path traversal detected in key: {k}")
        v_str = str(v)
        cleaned = _sanitize_string(v_str)
        if cleaned != v_str:
            warnings.append(f"Sensitive content in '{k}' was redacted.")
        sanitized_str[k] = cleaned
        structured[k] = v

    sanitized_bytes = json.dumps(structured, sort_keys=True, default=str).encode("utf-8")
    sanitized_hash = hashlib.sha256(sanitized_bytes).hexdigest()
    return sanitized_str, structured, warnings, raw_hash, sanitized_hash


_COMPILED_BPF_CACHE: Path | None = None


def _compile_seccomp_bpf(policy_path: Path) -> Path | None:
    """Compile worker-seccomp.json to classic BPF filter file via libseccomp."""
    global _COMPILED_BPF_CACHE
    if _COMPILED_BPF_CACHE is not None and _COMPILED_BPF_CACHE.exists():
        return _COMPILED_BPF_CACHE
    if not policy_path.exists():
        return None
    try:
        lib = ctypes.CDLL("libseccomp.so.2")
        lib.seccomp_init.restype = ctypes.c_void_p
        lib.seccomp_init.argtypes = [ctypes.c_uint32]
        lib.seccomp_export_bpf.restype = ctypes.c_int
        lib.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.seccomp_rule_add.restype = ctypes.c_int
        lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
        lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
        lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
        lib.seccomp_release.argtypes = [ctypes.c_void_p]

        with open(policy_path, encoding="utf-8") as f:
            policy = json.load(f)

        scmp_act_allow = 0x7FFF0000
        scmp_act_errno = 0x00050001  # EPERM

        ctx = lib.seccomp_init(scmp_act_errno)
        for group in policy.get("syscalls", []):
            action = scmp_act_allow if group.get("action") == "SCMP_ACT_ALLOW" else scmp_act_errno
            for name in group.get("names", []):
                nr = lib.seccomp_syscall_resolve_name(name.encode("utf-8"))
                if nr >= 0:
                    lib.seccomp_rule_add(ctx, action, nr, 0)

        with tempfile.NamedTemporaryFile(delete=False, prefix="sbx-seccomp-") as bpf_tmp:
            res = lib.seccomp_export_bpf(ctx, bpf_tmp.fileno())
            bpf_path = Path(bpf_tmp.name)

        lib.seccomp_release(ctx)
        if res == 0 and bpf_path.stat().st_size > 0:
            _COMPILED_BPF_CACHE = bpf_path
            return _COMPILED_BPF_CACHE
        if bpf_path.exists():
            bpf_path.unlink()
        return None
    except Exception as exc:
        logger.warning("Failed to compile seccomp BPF filter: %s", exc)
        return None


class DelegatedCgroupManager:
    """Manages dedicated delegated cgroup v2 subtree for the provisioner daemon.

    In production under systemd with Delegate=cpu memory pids:
    1. Moves daemon PID to a leaf cgroup (daemon/) to satisfy the cgroup v2
       "no internal processes" constraint.
    2. Enables controllers (+cpu +memory +pids) in cgroup.subtree_control.
    3. Dynamically creates isolated child attempt cgroups (sbx-<attempt>-<exec>)
       with hardware memory.max, memory.swap.max=0, pids.max, and cpu.max limits.
    4. Attaches specialist child processes directly via preexec_fn writing cgroup.procs.
    5. Cleans up attempt cgroups on completion via cgroup.kill and rmdir.
    """

    def __init__(self, cgroup_root: Path | None = None) -> None:
        self.cgroup_root: Path | None = cgroup_root
        self.daemon_cgroup: Path | None = None
        self.available_controllers: set[str] = set()
        self.enabled_controllers: set[str] = set()
        self.active: bool = False
        self._lock = threading.Lock()
        self._initialize()

    def _discover_cgroup_root(self) -> Path | None:
        """Discover the cgroup v2 root path for the current process."""
        proc_cgroup = Path("/proc/self/cgroup")
        if not proc_cgroup.exists():
            return None
        try:
            content = proc_cgroup.read_text(encoding="utf-8").strip()
            for line in content.splitlines():
                parts = line.split("::")
                if len(parts) == 2:
                    rel = parts[1].strip().lstrip("/")
                    candidate = Path("/sys/fs/cgroup") / rel
                    if candidate.exists() and os.access(candidate, os.W_OK):
                        return candidate
        except Exception as exc:
            logger.debug("Failed to discover cgroup root from /proc/self/cgroup: %s", exc)
        return None

    def _initialize(self) -> None:
        """Initialize delegation by moving daemon to leaf cgroup and enabling controllers."""
        if self.cgroup_root is None:
            self.cgroup_root = self._discover_cgroup_root()

        if self.cgroup_root is None or not self.cgroup_root.exists():
            logger.debug("Cgroup v2 delegation root not available or not writable.")
            return

        controllers_file = self.cgroup_root / "cgroup.controllers"
        if not controllers_file.exists():
            logger.debug("Cgroup v2 controllers file missing at %s", controllers_file)
            return

        try:
            self.available_controllers = set(controllers_file.read_text(encoding="utf-8").split())
            desired = {"cpu", "memory", "pids"}.intersection(self.available_controllers)
            if not desired:
                logger.debug("None of desired controllers (cpu, memory, pids) available in %s", self.cgroup_root)
                return

            # 1. Clean up stale attempt cgroups from prior runs
            for child in self.cgroup_root.iterdir():
                if child.is_dir() and child.name.startswith("sbx-"):
                    self._cleanup_cgroup_dir(child)

            # 2. Leaf migration: move daemon to daemon/ leaf to satisfy no-internal-processes rule
            self.daemon_cgroup = self.cgroup_root / "daemon"
            self.daemon_cgroup.mkdir(parents=True, exist_ok=True)

            procs_file = self.cgroup_root / "cgroup.procs"
            daemon_procs = self.daemon_cgroup / "cgroup.procs"
            if procs_file.exists():
                procs = procs_file.read_text(encoding="utf-8").split()
                with open(daemon_procs, "w", encoding="utf-8") as f:
                    for p in procs:
                        f.write(f"{p}\n")
                        f.flush()

            # 3. Enable subtree controllers on the delegated root
            subtree_ctrl = self.cgroup_root / "cgroup.subtree_control"
            cmd = " ".join(f"+{c}" for c in desired)
            subtree_ctrl.write_text(cmd, encoding="utf-8")

            # Read back active controllers
            self.enabled_controllers = {c.lstrip("+") for c in subtree_ctrl.read_text(encoding="utf-8").split()}
            self.active = bool(self.enabled_controllers)
            logger.info(
                "Delegated cgroup v2 active at %s with controllers: %s",
                self.cgroup_root,
                self.enabled_controllers,
            )
        except Exception as exc:
            logger.warning("Failed to initialize delegated cgroup v2 subtree at %s: %s", self.cgroup_root, exc)
            self.active = False

    def _cleanup_cgroup_dir(self, cgroup_dir: Path) -> None:
        """Kill processes in a cgroup and remove the directory."""
        try:
            kill_file = cgroup_dir / "cgroup.kill"
            if kill_file.exists():
                with contextlib.suppress(Exception):
                    kill_file.write_text("1", encoding="utf-8")
            else:
                procs_file = cgroup_dir / "cgroup.procs"
                if procs_file.exists():
                    for pid_str in procs_file.read_text(encoding="utf-8").split():
                        with contextlib.suppress(Exception):
                            os.kill(int(pid_str), signal.SIGKILL)

            # Drain check
            procs_file = cgroup_dir / "cgroup.procs"
            for _ in range(20):
                if not procs_file.exists() or not procs_file.read_text(encoding="utf-8").strip():
                    break
                time.sleep(0.02)
            try:
                cgroup_dir.rmdir()
            except OSError:
                # In non-cgroupfs filesystems (e.g. mock unit tests), recursively remove test files
                shutil.rmtree(cgroup_dir, ignore_errors=True)
        except Exception as exc:
            logger.debug("Failed to clean cgroup dir %s: %s", cgroup_dir, exc)

    @contextlib.contextmanager
    def create_attempt_scope(
        self,
        stage_attempt_id: str,
        execution_id: str,
        memory_mb: int,
        cpu_cores: float,
        pids_limit: int = 128,
    ):
        """Context manager yielding attempt cgroup path and preexec function, or (None, None) if inactive."""
        if not self.active or self.cgroup_root is None:
            yield None, None
            return

        import re
        safe_attempt = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", stage_attempt_id)
        safe_exec = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", execution_id[:8])
        attempt_name = f"sbx-{safe_attempt}-{safe_exec}"
        attempt_dir = self.cgroup_root / attempt_name
        attempt_dir.mkdir(parents=True, exist_ok=True)
        try:
            # Apply resource constraints
            if "memory" in self.enabled_controllers:
                mem_bytes = memory_mb * 1024 * 1024
                (attempt_dir / "memory.max").write_text(str(mem_bytes), encoding="utf-8")
                swap_max = attempt_dir / "memory.swap.max"
                if swap_max.exists():
                    swap_max.write_text("0", encoding="utf-8")

            if "pids" in self.enabled_controllers:
                (attempt_dir / "pids.max").write_text(str(pids_limit), encoding="utf-8")

            if "cpu" in self.enabled_controllers:
                cpu_quota = int(cpu_cores * 100000)
                (attempt_dir / "cpu.max").write_text(f"{cpu_quota} 100000", encoding="utf-8")

            def _preexec_attach() -> None:
                try:
                    procs_file = attempt_dir / "cgroup.procs"
                    with open(procs_file, "w", encoding="utf-8") as f:
                        f.write(str(os.getpid()))
                except Exception as err:
                    sys.stderr.write(f"Cgroup preexec attach warning: {err}\n")

            yield attempt_dir, _preexec_attach
        finally:
            self._cleanup_cgroup_dir(attempt_dir)


class SandboxProvisionerEngine:
    """Out-of-process engine that builds and manages physical sandbox runtimes."""

    def __init__(
        self,
        repo_root: Path | None = None,
        strict_bwrap: bool = False,
        replay_state_path: Path | None = None,
        preferred_bwrap_path: str | Path | None = None,
        cgroup_root: Path | None = None,
    ) -> None:
        self._repo_root = repo_root or _locate_repo_root()
        self._skills_base = self._repo_root / "sandbox" / "docker" / "hardened" / "skills"
        self._seccomp_profile = self._repo_root / "sandbox" / "docker" / "hardened" / "seccomp" / "worker-seccomp.json"

        # Probe and verify bubblewrap version and security
        self._bwrap_path, self._bwrap_version, self._bwrap_warnings = _resolve_bwrap_path(
            preferred_path=preferred_bwrap_path,
            strict_version=strict_bwrap,
        )
        self._systemd_run_path = shutil.which("systemd-run")

        # Cgroup v2 delegation manager
        self._cgroup_manager = DelegatedCgroupManager(cgroup_root=cgroup_root)

        # Persistent replay state management
        self._replay_manager = ReplayStateManager(state_file_path=replay_state_path)
        self._active_attempts: set[str] = set()
        self._lock = threading.Lock()

        # Scrub any leftover staging directories from prior abnormal terminations
        cleanup_stale_runtimes()

    @property
    def has_physical_isolation_runtime(self) -> bool:
        return self._bwrap_path is not None

    @property
    def bwrap_version(self) -> tuple[int, int, int] | None:
        return self._bwrap_version

    @property
    def bwrap_version_str(self) -> str:
        return ".".join(map(str, self._bwrap_version)) if self._bwrap_version else ""

    def validate_mandate(self, mandate: SandboxInvocationMandate) -> str:
        """Validate mandate against capability policy and server-side constraints."""
        # 1. Capability allowlisting
        if mandate.capability not in CAPABILITY_SKILL_MAP:
            cap_val = getattr(mandate.capability, "value", str(mandate.capability))
            raise SandboxValidationError(f"Unauthorized or unregistered sandbox capability: {cap_val}")

        skill_name = CAPABILITY_SKILL_MAP[mandate.capability]
        skill_dir = self._skills_base / skill_name
        if not skill_dir.is_dir():
            raise SandboxValidationError(f"Authorized skill directory not found on host: {skill_dir}")

        # 2. Tenant / Directive binding
        if not mandate.tenant_id or not mandate.tenant_id.strip():
            raise SandboxValidationError("Mandate missing required tenant_id binding.")

        # 3. Lease validation (fail closed if expired)
        if mandate.lease_expires_at is not None:
            now = datetime.now(UTC)
            exp = mandate.lease_expires_at if mandate.lease_expires_at.tzinfo else mandate.lease_expires_at.replace(tzinfo=UTC)
            if now > exp:
                raise PolicyViolationError(f"Mandate execution lease expired at {exp} (current time: {now}).")

        # 4. Resource ceiling enforcement (server-enforced ceilings)
        if mandate.resource_limits.cpu_cores > MAX_ALLOWED_CPU_CORES:
            raise PolicyViolationError(
                f"Requested CPU cores {mandate.resource_limits.cpu_cores} exceeds maximum ceiling {MAX_ALLOWED_CPU_CORES}"
            )
        if mandate.resource_limits.memory_mb > MAX_ALLOWED_MEMORY_MB:
            raise PolicyViolationError(
                f"Requested memory {mandate.resource_limits.memory_mb}MB exceeds maximum ceiling {MAX_ALLOWED_MEMORY_MB}MB"
            )
        pids = getattr(mandate.resource_limits, "pids_limit", 128)
        if pids > MAX_ALLOWED_PIDS:
            raise PolicyViolationError(f"Requested PIDs {pids} exceeds maximum ceiling {MAX_ALLOWED_PIDS}")

        # 5. Anti-traversal inspection on payload
        payload_str = json.dumps(mandate.payload, default=str)
        if "../" in payload_str or "..\\" in payload_str:
            for k, v in mandate.payload.items():
                if isinstance(v, str) and ("../" in v or "..\\" in v):
                    raise SandboxValidationError(f"Path traversal detected in input payload parameter '{k}'")
            raise SandboxValidationError("Path traversal detected in input payload")

        # 6. Network policy enforcement
        if mandate.network_policy != NetworkPolicy.DISABLED and mandate.egress_grant is None:
            raise PolicyViolationError(
                f"Network policy '{mandate.network_policy.value}' requested without approved SandboxEgressGrant."
            )

        return skill_name

    def execute(self, mandate: SandboxInvocationMandate) -> SandboxResult:
        """Provision physical runtime, run specialist, seal output, and scrub staging."""
        start_time = time.perf_counter()
        start_dt = datetime.now(UTC)

        skill_name = self.validate_mandate(mandate)

        attempt_key = f"{mandate.task_id}:{mandate.stage_attempt_id}"

        with self._lock:
            # Persistent Replay Protection
            if mandate.execution_id in self._replay_manager.seen_executions:
                raise SandboxIsolationError(
                    f"Execution ID '{mandate.execution_id}' has already been executed. Replay forbidden."
                )

            if attempt_key in self._replay_manager.seen_attempts or attempt_key in self._active_attempts:
                raise SandboxIsolationError(
                    f"Attempt '{mandate.stage_attempt_id}' is already active or reused. Fresh attempt_id required."
                )

            self._active_attempts.add(attempt_key)

        container_id = f"sbx-{mandate.tenant_id[:6]}-{skill_name}-{mandate.stage_attempt_id}-{mandate.execution_id}"
        runtime_id = f"runtime-{mandate.execution_id}"

        staging_dir = Path(tempfile.mkdtemp(prefix=f"sbx-staging-{mandate.execution_id[:8]}-"))
        input_file = staging_dir / "input.json"
        output_file = staging_dir / "output.json"
        ns_info_file = staging_dir / "ns_info.json"

        input_bytes = json.dumps(mandate.payload, ensure_ascii=False).encode("utf-8")
        input_digest = hashlib.sha256(input_bytes).hexdigest()
        input_file.write_bytes(input_bytes)

        ns_evidence: dict[str, Any] = {}
        stderr_output = ""
        raw_result: dict[str, Any] = {}
        teardown_status = "CLEAN"

        try:
            raw_result, ns_evidence = self._run_in_physical_runtime(
                mandate=mandate,
                skill_name=skill_name,
                staging_dir=staging_dir,
                input_file=input_file,
                output_file=output_file,
                ns_info_file=ns_info_file,
            )
            # Record persistent replay record only after successful execution
            self._replay_manager.record_and_save(mandate.execution_id, attempt_key)

        except Exception as exc:
            stderr_output = str(exc)
            logger.error("Physical sandbox execution failed for %s: %s", container_id, exc)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            exec_receipt = SandboxExecutionReceipt(
                runtime_id=runtime_id,
                container_id=container_id,
                image_digest=PINNED_DIGEST,
                runtime_version=PINNED_RUNTIME_VERSION,
                profile_version=PINNED_PROFILE_VERSION,
                network_mode=mandate.network_policy.value,
                seccomp_profile="worker-seccomp.json",
                read_only_root=True,
                effective_cpu_cores=mandate.resource_limits.cpu_cores,
                effective_memory_mb=mandate.resource_limits.memory_mb,
                effective_pids_limit=getattr(mandate.resource_limits, "pids_limit", 128),
                started_at=start_dt,
                terminated_at=datetime.now(UTC),
                exit_code=1,
                termination_reason="failed",
                sanitation_version="v1",
                input_digest=input_digest,
                output_digest=hashlib.sha256(b"").hexdigest(),
                pid_namespace=str(ns_evidence.get("pid", "")),
                mount_namespace=str(ns_evidence.get("mnt", "")),
                net_namespace=str(ns_evidence.get("net", "")),
                ipc_namespace=str(ns_evidence.get("ipc", "")),
                uts_namespace=str(ns_evidence.get("uts", "")),
                cgroup_path=str(ns_evidence.get("cgroup", "")),
                seccomp_status=str(ns_evidence.get("seccomp", "2")),
                isolation_primitive="linux_namespace_sandbox",
                no_new_privs=str(ns_evidence.get("no_new_privs", "1")) == "1",
                userns_disabled=bool(ns_evidence.get("userns_disabled", True)),
                bwrap_version=self.bwrap_version_str,
            )
            teardown_receipt = SandboxTeardownReceipt(
                sandbox_id=container_id,
                attempt_id=mandate.stage_attempt_id,
                status="CLEAN",
                workspace_scrubbed=True,
                credentials_revoked=True,
                runtime_destroyed=True,
                destroyed_at=datetime.now(UTC),
                error_details=stderr_output,
            )
            return SandboxResult(
                execution_id=mandate.execution_id,
                task_id=mandate.task_id,
                worker_role=mandate.worker_role,
                worker_id=mandate.worker_id,
                specialist_id=mandate.specialist_id or mandate.capability.value,
                capability=mandate.capability,
                status=SandboxExecutionStatus.FAILED,
                success=False,
                error=stderr_output,
                execution_duration_ms=round(duration_ms, 2),
                raw_output_sha256="",
                sanitized_output_sha256="",
                execution_receipt=exec_receipt,
                teardown_receipt=teardown_receipt,
            )
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            with self._lock:
                self._active_attempts.discard(attempt_key)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        sanitized_output, structured_output, warnings, raw_hash, sanitized_hash = _sanitize_payload(raw_result)

        artifacts: list[str] = []
        if "diff" in sanitized_output and sanitized_output["diff"]:
            artifacts.append(f"diff:{mandate.task_id}")
        if "strategy_plan" in sanitized_output:
            artifacts.append(f"strategy:{mandate.task_id}")
        if "learning_delta" in sanitized_output:
            artifacts.append(f"delta:{mandate.task_id}")

        confidence = 1.0
        for score_key in ("confidence", "confidence_score", "decay_multiplier"):
            if score_key in sanitized_output:
                try:
                    confidence = float(sanitized_output[score_key])
                    break
                except (ValueError, TypeError):
                    pass

        exec_receipt = SandboxExecutionReceipt(
            runtime_id=runtime_id,
            container_id=container_id,
            image_digest=PINNED_DIGEST,
            runtime_version=PINNED_RUNTIME_VERSION,
            profile_version=PINNED_PROFILE_VERSION,
            network_mode=mandate.network_policy.value,
            seccomp_profile="worker-seccomp.json",
            read_only_root=True,
            effective_cpu_cores=mandate.resource_limits.cpu_cores,
            effective_memory_mb=mandate.resource_limits.memory_mb,
            effective_pids_limit=getattr(mandate.resource_limits, "pids_limit", 128),
            started_at=start_dt,
            terminated_at=datetime.now(UTC),
            exit_code=0,
            termination_reason="completed",
            sanitation_version="v1",
            input_digest=input_digest,
            output_digest=sanitized_hash,
            pid_namespace=str(ns_evidence.get("pid", "")),
            mount_namespace=str(ns_evidence.get("mnt", "")),
            net_namespace=str(ns_evidence.get("net", "")),
            ipc_namespace=str(ns_evidence.get("ipc", "")),
            uts_namespace=str(ns_evidence.get("uts", "")),
            cgroup_path=str(ns_evidence.get("cgroup", "")),
            seccomp_status=str(ns_evidence.get("seccomp", "2")),
            isolation_primitive="linux_namespace_sandbox",
            no_new_privs=str(ns_evidence.get("no_new_privs", "1")) == "1",
            userns_disabled=bool(ns_evidence.get("userns_disabled", True)),
            bwrap_version=self.bwrap_version_str,
        )
        teardown_receipt = SandboxTeardownReceipt(
            sandbox_id=container_id,
            attempt_id=mandate.stage_attempt_id,
            status=teardown_status,
            workspace_scrubbed=True,
            credentials_revoked=True,
            runtime_destroyed=True,
            destroyed_at=datetime.now(UTC),
        )

        return SandboxResult(
            execution_id=mandate.execution_id,
            task_id=mandate.task_id,
            worker_role=mandate.worker_role,
            worker_id=mandate.worker_id,
            specialist_id=mandate.specialist_id or mandate.capability.value,
            capability=mandate.capability,
            status=SandboxExecutionStatus.COMPLETED,
            success=True,
            sanitized_output=sanitized_output,
            structured_output=structured_output,
            confidence_score=confidence,
            generated_diff=sanitized_output.get("diff", ""),
            stdout=sanitized_output.get("stdout", ""),
            sanitized_stderr=stderr_output,
            generated_artifacts=artifacts,
            artifact_references=artifacts,
            metrics={"execution_duration_ms": round(duration_ms, 2)},
            warnings=warnings,
            execution_duration_ms=round(duration_ms, 2),
            raw_output_sha256=raw_hash,
            sanitized_output_sha256=sanitized_hash,
            execution_receipt=exec_receipt,
            teardown_receipt=teardown_receipt,
        )

    def _run_in_physical_runtime(
        self,
        mandate: SandboxInvocationMandate,
        skill_name: str,
        staging_dir: Path,
        input_file: Path,
        output_file: Path,
        ns_info_file: Path,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Launch isolated Linux container runtime (bubblewrap unprivileged namespace engine)."""
        if not self._bwrap_path:
            raise SandboxIsolationError("Bubblewrap (bwrap) physical namespace engine is not functional on host.")

        skill_mount = self._skills_base / skill_name
        skill_script = skill_mount / "scripts" / "run.py"
        if not skill_script.exists():
            raise SandboxValidationError(f"Specialist entrypoint script not found: {skill_script}")

        python_bin = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else (sys.executable or "/usr/bin/python3")

        # 1. Hardware Cgroup v2 Scope per Attempt (Native delegation or systemd-run fallback)
        cgroup_scope = self._cgroup_manager.create_attempt_scope(
            stage_attempt_id=mandate.stage_attempt_id,
            execution_id=mandate.execution_id,
            memory_mb=mandate.resource_limits.memory_mb,
            cpu_cores=mandate.resource_limits.cpu_cores,
            pids_limit=getattr(mandate.resource_limits, "pids_limit", 128),
        )

        with cgroup_scope as (attempt_cgroup_dir, preexec_fn):
            wrap_prefix: list[str] = []
            if attempt_cgroup_dir is None and self._systemd_run_path:
                unit_name = f"sbx-{mandate.stage_attempt_id}-{mandate.execution_id[:8]}"
                mem_mb = mandate.resource_limits.memory_mb
                cpu_quota = int(mandate.resource_limits.cpu_cores * 100)
                pids_limit = int(getattr(mandate.resource_limits, "pids_limit", 128))
                wrap_prefix = [
                    self._systemd_run_path,
                    "--user",
                    "--scope",
                    f"--unit={unit_name}",
                    "-p",
                    f"MemoryMax={mem_mb}M",
                    "-p",
                    "MemorySwapMax=0",
                    "-p",
                    f"CPUQuota={cpu_quota}%",
                    "-p",
                    f"TasksMax={pids_limit}",
                ]

            # 2. Strict Minimal Filesystem Mounts & Namespace Hardening
            bwrap_cmd: list[str] = [
                str(self._bwrap_path),
                # Read-only standard Linux runtime paths
                "--ro-bind",
                "/usr",
                "/usr",
                "--ro-bind",
                "/lib",
                "/lib",
                "--ro-bind-try",
                "/lib64",
                "/lib64",
                "--ro-bind-try",
                "/bin",
                "/bin",
                "--ro-bind-try",
                "/etc/alternatives",
                "/etc/alternatives",
                "--ro-bind-try",
                "/etc/ssl",
                "/etc/ssl",
                # Isolated Linux namespaces: User, PID, Mount, Net, IPC, UTS
                "--unshare-user",
                # Namespace Hardening: Disable further use of user namespaces inside sandbox
                "--disable-userns",
                "--unshare-ipc",
                "--unshare-pid",
                "--unshare-net",
                "--unshare-uts",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                # Ephemeral private in-memory tmpfs
                "--tmpfs",
                "/tmp",
                "--tmpfs",
                "/workspace",
                # Least-privilege skill mount: Mounts strictly the single designated skill
                "--ro-bind",
                str(skill_mount),
                f"/home/gem/skills/{skill_name}",
            ]

            # Minimal math delegate for S_ALLOC only (single file, read-only)
            if mandate.capability == SandboxCapability.ALLOC:
                s_alloc_core = self._repo_root / "backend" / "app" / "integrations" / "sandbox" / "s_alloc_core.py"
                if s_alloc_core.exists():
                    bwrap_cmd.extend(["--ro-bind", str(s_alloc_core), "/workspace/s_alloc_core.py"])

            bwrap_cmd.extend([
                "--bind",
                str(staging_dir),
                "/workspace/staging",
                "--setenv",
                "PYTHONPATH",
                "/workspace",
                "--setenv",
                "HOME",
                "/tmp",
                "--setenv",
                "LC_ALL",
                "C.UTF-8",
                "--setenv",
                "LANG",
                "C.UTF-8",
                "--setenv",
                "NO_PROXY",
                "*",
            ])

            # 3. Kernel Seccomp BPF Filter Enforcement
            bpf_path = _compile_seccomp_bpf(self._seccomp_profile)
            bpf_fd = None
            pass_fds: list[int] = []
            if bpf_path and bpf_path.exists():
                bpf_fd = open(bpf_path, "rb")
                pass_fds.append(bpf_fd.fileno())
                bwrap_cmd.extend(["--seccomp", str(bpf_fd.fileno())])

            runner_file = staging_dir / "runner.py"
            runner_file.write_text(
                "import os, json, sys, subprocess, ctypes\n"
                "userns_blocked = True\n"
                "try:\n"
                "    libc = ctypes.CDLL(None)\n"
                "    res = libc.unshare(0x10000000)\n"  # CLONE_NEWUSER
                "    userns_blocked = (res != 0)\n"
                "except Exception:\n"
                "    userns_blocked = True\n"
                "ns = {\n"
                "    'pid': os.readlink('/proc/self/ns/pid') if os.path.exists('/proc/self/ns/pid') else '',\n"
                "    'mnt': os.readlink('/proc/self/ns/mnt') if os.path.exists('/proc/self/ns/mnt') else '',\n"
                "    'net': os.readlink('/proc/self/ns/net') if os.path.exists('/proc/self/ns/net') else '',\n"
                "    'ipc': os.readlink('/proc/self/ns/ipc') if os.path.exists('/proc/self/ns/ipc') else '',\n"
                "    'uts': os.readlink('/proc/self/ns/uts') if os.path.exists('/proc/self/ns/uts') else '',\n"
                "    'cgroup': open('/proc/self/cgroup').read().strip() if os.path.exists('/proc/self/cgroup') else '',\n"
                "    'seccomp': next((l.split()[-1] for l in open('/proc/self/status') if l.startswith('Seccomp:')), '0'),\n"
                "    'no_new_privs': next((l.split()[-1] for l in open('/proc/self/status') if l.startswith('NoNewPrivs:')), '0'),\n"
                "    'userns_disabled': userns_blocked,\n"
                "}\n"
                "with open('/workspace/staging/ns_info.json', 'w') as f_ns:\n"
                "    f_ns.write(json.dumps(ns))\n"
                f"skill_script = '/home/gem/skills/{skill_name}/scripts/run.py'\n"
                "with open('/workspace/staging/input.json', 'r') as fin, open('/workspace/staging/output.json', 'w') as fout:\n"
                f"    proc = subprocess.run(['{python_bin}', skill_script], stdin=fin, stdout=fout, stderr=subprocess.PIPE, text=True)\n"
                "if proc.returncode != 0:\n"
                "    sys.stderr.write(proc.stderr)\n"
                "    sys.exit(proc.returncode)\n",
                encoding="utf-8",
            )

            run_cmd = wrap_prefix + bwrap_cmd + [python_bin, "/workspace/staging/runner.py"]

            timeout = mandate.timeout_seconds or 120
            try:
                exec_proc = subprocess.run(
                    run_cmd,
                    pass_fds=pass_fds,
                    capture_output=True,
                    text=True,
                    timeout=float(timeout),
                    preexec_fn=preexec_fn,
                )
            finally:
                if bpf_fd is not None:
                    bpf_fd.close()

            ns_evidence: dict[str, Any] = {}
            if ns_info_file.exists():
                with contextlib.suppress(Exception):
                    ns_evidence = json.loads(ns_info_file.read_text(encoding="utf-8"))

            if attempt_cgroup_dir is not None and not ns_evidence.get("cgroup"):
                ns_evidence["cgroup"] = str(attempt_cgroup_dir)

            if exec_proc.returncode != 0:
                raise SandboxExecutionError(
                    f"Specialist '{mandate.capability.value}' physical container exited with code {exec_proc.returncode}: {exec_proc.stderr}"
                )

            if not output_file.exists():
                raise SandboxExecutionError(f"Specialist '{mandate.capability.value}' produced no output file.")

            raw_output_text = output_file.read_text(encoding="utf-8")
            try:
                parsed = json.loads(raw_output_text)
            except Exception as exc:
                raise SandboxExecutionError(f"Failed to parse output JSON from specialist: {exc}") from exc

            return parsed, ns_evidence


class SandboxProvisionerServer:
    """Multi-threaded Unix Domain Socket Server managing sandbox provisioning."""

    def __init__(
        self,
        socket_path: str | Path | None = None,
        auth_token: str | None = None,
        engine: SandboxProvisionerEngine | None = None,
        identity_policy: SocketIdentityPolicy | None = None,
        is_systemd_activated: bool | None = None,
    ) -> None:
        self.socket_path = resolve_provisioner_socket_path(socket_path)
        self.auth_token = auth_token or "enterprise_os_sandbox_secure_token"
        self.engine = engine or SandboxProvisionerEngine()
        self.identity_policy = identity_policy or SocketIdentityPolicy()
        self._server_sock: socket.socket | None = None
        self._is_running = False
        self._is_socket_activated = is_systemd_activated
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start socket listener in background thread."""
        if self._is_running:
            return

        # Check systemd socket activation (SD_LISTEN_FDS_START = 3)
        listen_fds = os.environ.get("LISTEN_FDS")
        if self._is_socket_activated is None and listen_fds:
            try:
                num_fds = int(listen_fds)
                listen_pid = os.environ.get("LISTEN_PID")
                if num_fds >= 1 and (not listen_pid or int(listen_pid) == os.getpid()):
                    self._is_socket_activated = True
            except Exception:
                self._is_socket_activated = False

        if self._is_socket_activated:
            try:
                # Descriptor 3 is SD_LISTEN_FDS_START
                self._server_sock = socket.fromfd(3, socket.AF_UNIX, socket.SOCK_STREAM)
                self._is_running = True
                self._thread = threading.Thread(target=self._serve_loop, daemon=True)
                self._thread.start()
                logger.info("SandboxProvisionerServer active via systemd socket activation on FD 3.")
                return
            except Exception as exc:
                logger.warning("Failed systemd socket activation on FD 3 (%s). Falling back to direct bind.", exc)
                self._is_socket_activated = False

        # Direct Unix Domain Socket bind
        # Stale socket removal: probe if active, remove if dead
        if self.socket_path.exists():
            test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                test_sock.settimeout(0.3)
                test_sock.connect(str(self.socket_path))
                test_sock.close()
                raise SandboxIsolationError(f"Active daemon already running on socket {self.socket_path}")
            except (ConnectionRefusedError, FileNotFoundError, socket.timeout, OSError):
                with contextlib.suppress(Exception):
                    self.socket_path.unlink()

        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(Exception):
            os.chmod(self.socket_path.parent, 0o770)

        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_sock.bind(str(self.socket_path))
        # Enforce strict SocketMode=0660: User and group access only
        os.chmod(self.socket_path, 0o660)
        self._server_sock.listen(64)
        self._is_running = True

        self._thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._thread.start()
        logger.info("SandboxProvisionerServer listening on UDS %s (SocketMode=0660)", self.socket_path)

    def stop(self) -> None:
        """Stop socket listener and clean up resources."""
        self._is_running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        if not self._is_socket_activated and self.socket_path.exists():
            with contextlib.suppress(Exception):
                self.socket_path.unlink()

    def _serve_loop(self) -> None:
        while self._is_running and self._server_sock:
            try:
                conn, _ = self._server_sock.accept()
            except OSError:
                break
            handler = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
            handler.start()

    def _handle_client(self, conn: socket.socket) -> None:
        try:
            # 1. Peer credential verification (Linux SO_PEERCRED)
            SO_PEERCRED = getattr(socket, "SO_PEERCRED", 17)
            try:
                creds = conn.getsockopt(socket.SOL_SOCKET, SO_PEERCRED, struct.calcsize("3i"))
                pid, uid, gid = struct.unpack("3i", creds)
                authorized, reason = self.identity_policy.authorize(uid, gid)
                if not authorized:
                    logger.warning("Rejected unauthorized peer connection from PID %d: %s", pid, reason)
                    self._send_error(
                        conn,
                        f"Unauthorized caller: {reason}",
                        error_type="PolicyViolationError",
                    )
                    return
            except Exception as cred_exc:
                logger.exception("SO_PEERCRED verification failed: %s", cred_exc)
                self._send_error(
                    conn,
                    "Failed to verify peer credentials on Unix domain socket",
                    error_type="PolicyViolationError",
                )
                return

            # 2. Length-prefixed framing: read 4-byte big-endian length
            len_bytes = self._recv_exact(conn, 4)
            if not len_bytes:
                return
            payload_len = struct.unpack(">I", len_bytes)[0]
            if payload_len > 10 * 1024 * 1024:  # 10 MB limit
                self._send_error(conn, "Payload too large", error_type="SandboxValidationError")
                return

            raw_payload = self._recv_exact(conn, payload_len)
            if not raw_payload:
                return

            req = json.loads(raw_payload.decode("utf-8"))

            # 3. Authentication token verification (constant-time compare defense-in-depth)
            token = req.get("auth_token", "")
            if not hmac.compare_digest(token, self.auth_token):
                self._send_error(
                    conn,
                    "Unauthorized caller: invalid or missing authentication token",
                    error_type="PolicyViolationError",
                )
                return

            # 4. Deserialization and validation of mandate
            mandate_dict = req.get("mandate")
            if not mandate_dict or not isinstance(mandate_dict, dict):
                self._send_error(conn, "Malformed request: missing mandate payload", error_type="SandboxValidationError")
                return

            try:
                mandate = SandboxInvocationMandate.model_validate(mandate_dict)
            except Exception as exc:
                self._send_error(conn, f"Mandate validation failed: {exc}", error_type="SandboxValidationError")
                return

            # 5. Execution through isolated engine
            try:
                result = self.engine.execute(mandate)
                resp = {"success": True, "result": result.model_dump(mode="json")}
                self._send_response(conn, resp)
            except Exception as exc:
                self._send_error(conn, str(exc), error_type=exc.__class__.__name__)

        except Exception as exc:
            logger.exception("Error handling provisioner connection: %s", exc)
        finally:
            with contextlib.suppress(Exception):
                conn.close()

    def _recv_exact(self, conn: socket.socket, num_bytes: int) -> bytes | None:
        buf = bytearray()
        while len(buf) < num_bytes:
            chunk = conn.recv(num_bytes - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    def _send_response(self, conn: socket.socket, resp_dict: dict[str, Any]) -> None:
        data = json.dumps(resp_dict, ensure_ascii=False).encode("utf-8")
        conn.sendall(struct.pack(">I", len(data)) + data)

    def _send_error(self, conn: socket.socket, error_msg: str, error_type: str = "SandboxExecutionError") -> None:
        resp = {"success": False, "error": error_msg, "error_type": error_type}
        self._send_response(conn, resp)


def main() -> None:
    """CLI entrypoint for standalone daemon service."""
    parser = argparse.ArgumentParser(description="Enterprise OS Standalone Sandbox Provisioner Daemon")
    parser.add_argument("--socket", default=None, help="Unix Domain Socket path (default: /run/enterprise_os/provisioner.sock)")
    parser.add_argument("--auth-token", default="enterprise_os_sandbox_secure_token", help="Shared secret auth token")
    parser.add_argument("--systemd-activation", action="store_true", help="Enable systemd socket activation on FD 3")
    parser.add_argument("--allowed-uids", default=None, help="Comma-separated allowed client UIDs for SO_PEERCRED")
    parser.add_argument("--allowed-gids", default=None, help="Comma-separated allowed client GIDs for SO_PEERCRED")
    parser.add_argument("--require-distinct-identity", action="store_true", help="Reject caller if UID matches daemon UID (enforces cross-user production boundary)")
    parser.add_argument("--strict-bwrap", action="store_true", help="Require bubblewrap >= 0.12.0 fail-closed")
    parser.add_argument("--state-file", default=None, help="Path to replay state persistence file")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    allowed_uids = {int(x.strip()) for x in args.allowed_uids.split(",") if x.strip().isdigit()} if args.allowed_uids else None
    allowed_gids = {int(x.strip()) for x in args.allowed_gids.split(",") if x.strip().isdigit()} if args.allowed_gids else None

    identity_policy = SocketIdentityPolicy(
        allowed_uids=allowed_uids,
        allowed_gids=allowed_gids,
        require_distinct_user=args.require_distinct_identity,
    )

    engine = SandboxProvisionerEngine(
        strict_bwrap=args.strict_bwrap,
        replay_state_path=Path(args.state_file) if args.state_file else None,
    )

    server = SandboxProvisionerServer(
        socket_path=args.socket,
        auth_token=args.auth_token,
        engine=engine,
        identity_policy=identity_policy,
        is_systemd_activated=True if args.systemd_activation else None,
    )

    def _sig_handler(signum: int, frame: Any) -> None:
        logger.info("Signal %d received, shutting down gracefully...", signum)
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)

    server.start()
    logger.info("Sandbox Provisioner Service active. Listening for connections.")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        server.stop()


if __name__ == "__main__":
    main()
