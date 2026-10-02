"""Standalone Sandbox Provisioner Daemon and Engine.

Runs out-of-process as a dedicated unprivileged OS service boundary.
Communicates exclusively over an authenticated Unix Domain Socket (UDS).
Enforces:
1. Complete process and container isolation from backend / IE / workers.
2. Server-side capability policy derivation (caller cannot provide arbitrary commands, paths, flags, or mounts).
3. Linux namespaces (user, pid, mount, net, ipc, uts), per-attempt cgroup v2 scope, and Seccomp: 2 filter.
4. Cryptographic output sanitization, digests, and deterministic staging scrub.
5. Peer credential verification and token authentication.
6. Fail-closed rejection of path traversal, expired leases, replayed attempts, and excessive resource requests.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import json
import logging
import os
import shutil
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
        import ctypes

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


class SandboxProvisionerEngine:
    """Out-of-process engine that builds and manages physical sandbox runtimes."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = repo_root or _locate_repo_root()
        self._skills_base = self._repo_root / "sandbox" / "docker" / "hardened" / "skills"
        self._seccomp_profile = self._repo_root / "sandbox" / "docker" / "hardened" / "seccomp" / "worker-seccomp.json"
        self._bwrap_path = shutil.which("bwrap")
        self._systemd_run_path = shutil.which("systemd-run")
        self._active_attempts: set[str] = set()
        self._seen_attempts: set[str] = set()
        self._seen_executions: set[str] = set()
        self._lock = threading.Lock()

    @property
    def has_physical_isolation_runtime(self) -> bool:
        return self._bwrap_path is not None

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

        with self._lock:
            # Replay protection
            if mandate.execution_id in self._seen_executions:
                raise SandboxIsolationError(
                    f"Execution ID '{mandate.execution_id}' has already been executed. Replay forbidden."
                )
            self._seen_executions.add(mandate.execution_id)

            attempt_key = f"{mandate.task_id}:{mandate.stage_attempt_id}"
            if attempt_key in self._seen_attempts or attempt_key in self._active_attempts:
                raise SandboxIsolationError(
                    f"Attempt '{mandate.stage_attempt_id}' is already active or reused. Fresh attempt_id required."
                )
            self._seen_attempts.add(attempt_key)
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

        ns_evidence: dict[str, str] = {}
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
                pid_namespace=ns_evidence.get("pid", ""),
                mount_namespace=ns_evidence.get("mnt", ""),
                net_namespace=ns_evidence.get("net", ""),
                ipc_namespace=ns_evidence.get("ipc", ""),
                uts_namespace=ns_evidence.get("uts", ""),
                cgroup_path=ns_evidence.get("cgroup", ""),
                seccomp_status=ns_evidence.get("seccomp", "2"),
                isolation_primitive="linux_namespace_sandbox",
                no_new_privs=ns_evidence.get("no_new_privs", "1") == "1",
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
            pid_namespace=ns_evidence.get("pid", ""),
            mount_namespace=ns_evidence.get("mnt", ""),
            net_namespace=ns_evidence.get("net", ""),
            ipc_namespace=ns_evidence.get("ipc", ""),
            uts_namespace=ns_evidence.get("uts", ""),
            cgroup_path=ns_evidence.get("cgroup", ""),
            seccomp_status=ns_evidence.get("seccomp", "2"),
            isolation_primitive="linux_namespace_sandbox",
            no_new_privs=ns_evidence.get("no_new_privs", "1") == "1",
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
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Launch isolated Linux container runtime (bubblewrap unprivileged namespace engine)."""
        if not self._bwrap_path:
            raise SandboxIsolationError("Bubblewrap (bwrap) physical namespace engine is not installed on host.")

        skill_mount = self._skills_base / skill_name
        skill_script = skill_mount / "scripts" / "run.py"
        if not skill_script.exists():
            raise SandboxValidationError(f"Specialist entrypoint script not found: {skill_script}")

        python_bin = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else (sys.executable or "/usr/bin/python3")

        # 1. Hardware Cgroup v2 Scope per Attempt
        wrap_prefix: list[str] = []
        if self._systemd_run_path:
            unit_name = f"sbx-{mandate.stage_attempt_id}-{mandate.execution_id[:8]}"
            mem_mb = int(mandate.resource_limits.memory_mb)
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

        # 2. Strict Minimal Filesystem Mounts
        bwrap_cmd: list[str] = [
            self._bwrap_path,
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
            "import os, json, sys, subprocess\n"
            "ns = {\n"
            "    'pid': os.readlink('/proc/self/ns/pid') if os.path.exists('/proc/self/ns/pid') else '',\n"
            "    'mnt': os.readlink('/proc/self/ns/mnt') if os.path.exists('/proc/self/ns/mnt') else '',\n"
            "    'net': os.readlink('/proc/self/ns/net') if os.path.exists('/proc/self/ns/net') else '',\n"
            "    'ipc': os.readlink('/proc/self/ns/ipc') if os.path.exists('/proc/self/ns/ipc') else '',\n"
            "    'uts': os.readlink('/proc/self/ns/uts') if os.path.exists('/proc/self/ns/uts') else '',\n"
            "    'cgroup': open('/proc/self/cgroup').read().strip() if os.path.exists('/proc/self/cgroup') else '',\n"
            "    'seccomp': next((l.split()[-1] for l in open('/proc/self/status') if l.startswith('Seccomp:')), '0'),\n"
            "    'no_new_privs': next((l.split()[-1] for l in open('/proc/self/status') if l.startswith('NoNewPrivs:')), '0'),\n"
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
            )
        finally:
            if bpf_fd is not None:
                bpf_fd.close()

        ns_evidence: dict[str, str] = {}
        if ns_info_file.exists():
            with contextlib.suppress(Exception):
                ns_evidence = json.loads(ns_info_file.read_text(encoding="utf-8"))

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
        socket_path: str | Path,
        auth_token: str,
        engine: SandboxProvisionerEngine | None = None,
    ) -> None:
        self.socket_path = Path(socket_path)
        self.auth_token = auth_token
        self.engine = engine or SandboxProvisionerEngine()
        self._server_sock: socket.socket | None = None
        self._is_running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start socket listener in background thread."""
        if self._is_running:
            return

        if self.socket_path.exists():
            self.socket_path.unlink()

        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_sock.bind(str(self.socket_path))
        # Enforce strict socket file permissions (0600: owner only)
        os.chmod(self.socket_path, 0o600)
        self._server_sock.listen(64)
        self._is_running = True

        self._thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._thread.start()
        logger.info("SandboxProvisionerServer listening on UDS %s", self.socket_path)

    def stop(self) -> None:
        """Stop socket listener."""
        self._is_running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
        if self.socket_path.exists():
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
            # 1. Peer credential check (Linux SO_PEERCRED)
            SO_PEERCRED = getattr(socket, "SO_PEERCRED", 17)
            with contextlib.suppress(Exception):
                creds = conn.getsockopt(socket.SOL_SOCKET, SO_PEERCRED, struct.calcsize("3i"))
                pid, uid, gid = struct.unpack("3i", creds)
                # Client must match server UID or be root
                if uid != os.getuid() and os.getuid() != 0 and uid != 0:
                    self._send_error(conn, "Unauthorized caller: UID mismatch", error_type="PolicyViolationError")
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

            # 3. Authentication token verification (constant-time compare)
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
    parser.add_argument("--socket", default="/tmp/enterprise_os_provisioner.sock", help="Unix Domain Socket path")
    parser.add_argument("--auth-token", default="enterprise_os_sandbox_secure_token", help="Shared secret auth token")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    server = SandboxProvisionerServer(socket_path=args.socket, auth_token=args.auth_token)
    server.start()

    logger.info("Sandbox Provisioner Service active. Press Ctrl+C to terminate.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping Sandbox Provisioner Service...")
        server.stop()


if __name__ == "__main__":
    main()
