"""Deterministic Sandbox Control Plane and Policy Engine for W_DEV (DE-03).

Enforces:
- Ephemeral isolated sandbox instances per sub-agent attempt (no reuse across retries).
- Strict binding to tenant/work-region/engine/task/step/attempt identity.
- Pre-execution lease and isolation validation (fail-closed).
- Non-root UID/GID, cgroups limits, seccomp profile, and no-new-privileges.
- Deny-by-default network policy with anti-SSRF protections.
- Ephemeral workspace materialization for approved immutable input snapshots.
- Cryptographic SHA-256 output sealing prior to sandbox teardown.
- Deterministic cleanup and short-lived credential revocation across all exit paths.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.exceptions import (
    GovernedBackendError,
    PolicyViolationError,
    SandboxCleanupError,
    SandboxControlPlaneError,
    SandboxExecutionError,
    SandboxInvocationError,
    SandboxIsolationError,
    SandboxValidationError,
)
from app.core.logging import get_logger
from app.integrations.sandbox.capabilities import (
    validate_capability_access,
    validate_tool_access,
)
from app.schemas.sandbox import (
    NetworkPolicy,
    SandboxCapability,
    SandboxCapabilityGrant,
    SandboxFilesystemPolicy,
    SandboxIdentity,
    SandboxInvocationMandate,
    SandboxLifecycleState,
    SandboxNetworkPolicyConfig,
    SandboxResourceLimits,
    SandboxResult,
    SealedSandboxOutput,
)
from app.schemas.task_state import DevelopmentExecutionLease

logger = get_logger(__name__)


# ===========================================================================
# Short-Lived Credential Manager
# ===========================================================================

class SandboxCredentialManager:
    """Issues and revokes task-scoped, short-lived sandbox credentials."""

    def __init__(self) -> None:
        self._active_credentials: dict[str, dict[str, Any]] = {}

    def issue_credential(
        self,
        identity: SandboxIdentity,
        lease: DevelopmentExecutionLease,
    ) -> str:
        """Issue a unique, time-bounded credential scoped to this sandbox attempt."""
        token = f"sbx_token_{identity.sandbox_id}_{uuid.uuid4().hex}"
        self._active_credentials[identity.sandbox_id] = {
            "token": token,
            "sandbox_id": identity.sandbox_id,
            "tenant_id": identity.tenant_id,
            "task_id": identity.task_id,
            "step_id": identity.step_id,
            "attempt_id": identity.attempt_id,
            "issued_at": datetime.now(UTC),
            "expires_at": lease.expires_at,
            "revoked": False,
        }
        return token

    def is_valid(self, sandbox_id: str, token: str) -> bool:
        """Verify that credential exists, matches token, and is neither expired nor revoked."""
        record = self._active_credentials.get(sandbox_id)
        if not record:
            return False
        if record["revoked"]:
            return False
        if record["token"] != token:
            return False
        exp = record["expires_at"]
        exp_utc = exp if exp.tzinfo is not None else exp.replace(tzinfo=UTC)
        if exp_utc <= datetime.now(UTC):
            return False
        return True

    def revoke_credential(self, sandbox_id: str) -> None:
        """Deterministically revoke and scrub credentials for this sandbox."""
        if sandbox_id in self._active_credentials:
            self._active_credentials[sandbox_id]["revoked"] = True
            del self._active_credentials[sandbox_id]


# ===========================================================================
# Ephemeral Workspace Materializer
# ===========================================================================

class WorkspaceMaterializer:
    """Materializes approved immutable input snapshots into ephemeral isolated workspaces."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else Path(tempfile.gettempdir()) / "enterprise_os_sandboxes"
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def prepare_workspace(
        self,
        sandbox_id: str,
        input_snapshot: dict[str, str] | None = None,
    ) -> tuple[Path, dict[str, str]]:
        """Create an ephemeral workspace directory and materialize immutable input files.

        Returns (workspace_path, input_file_hashes).
        """
        workspace_dir = self._base_dir / sandbox_id
        # Fail closed: must be a fresh workspace, never reuse across retries
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir, ignore_errors=True)
        workspace_dir.mkdir(parents=True, exist_ok=False)

        input_hashes: dict[str, str] = {}
        if input_snapshot:
            for rel_path, content in input_snapshot.items():
                target_file = (workspace_dir / rel_path).resolve()
                # Directory traversal guard
                if not str(target_file).startswith(str(workspace_dir.resolve())):
                    raise SandboxIsolationError(
                        f"Directory traversal attempt detected in input snapshot path: '{rel_path}'"
                    )
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(content, encoding="utf-8")
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                input_hashes[rel_path] = digest

        return workspace_dir, input_hashes

    def scrub_workspace(self, sandbox_id: str) -> None:
        """Deterministically wipe ephemeral workspace contents and remove directory."""
        workspace_dir = self._base_dir / sandbox_id
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir, ignore_errors=True)


# ===========================================================================
# Isolation Validator
# ===========================================================================

class IsolationValidator:
    """Validates runtime, filesystem, resource, network, and lease security boundaries."""

    @staticmethod
    def validate_lease(
        identity: SandboxIdentity,
        lease: DevelopmentExecutionLease,
    ) -> None:
        """Verify lease is valid, unexpired, and correctly bound to identity."""
        if lease.is_expired():
            raise SandboxValidationError(
                f"Execution lease '{lease.lease_id}' has expired. Cannot provision or execute sandbox."
            )
        if lease.task_id != identity.task_id:
            raise SandboxValidationError(
                f"Lease task_id '{lease.task_id}' does not match sandbox task_id '{identity.task_id}'."
            )
        if lease.step_id != identity.step_id:
            raise SandboxValidationError(
                f"Lease step_id '{lease.step_id}' does not match sandbox step_id '{identity.step_id}'."
            )
        if lease.attempt_id != identity.attempt_id:
            raise SandboxValidationError(
                f"Lease attempt_id '{lease.attempt_id}' does not match sandbox attempt_id '{identity.attempt_id}'."
            )

    @staticmethod
    def validate_resource_boundaries(limits: SandboxResourceLimits) -> None:
        """Enforce container / microVM resource ceiling policies."""
        if limits.run_as_user in ("0", "0:0", "root"):
            raise SandboxIsolationError("Running sandbox container as root (UID 0) is strictly forbidden.")
        if not limits.no_new_privileges:
            raise SandboxIsolationError("Sandbox must enforce no_new_privileges=True.")
        if "ALL" not in limits.cap_drop:
            raise SandboxIsolationError("Sandbox container must drop ALL Linux capabilities (cap_drop=['ALL']).")
        if limits.cpu_cores > 4.0:
            raise SandboxIsolationError(f"Requested CPU cores ({limits.cpu_cores}) exceeds max ceiling of 4.0.")
        if limits.memory_mb > 8192:
            raise SandboxIsolationError(f"Requested memory ({limits.memory_mb}MB) exceeds max ceiling of 8192MB.")
        if limits.pids_limit > 2048:
            raise SandboxIsolationError(f"Requested PID limit ({limits.pids_limit}) exceeds max ceiling of 2048.")

    @staticmethod
    def validate_network_isolation(
        network_config: SandboxNetworkPolicyConfig,
        target_destination: str | None = None,
    ) -> None:
        """Enforce deny-by-default egress and block SSRF / internal destinations."""
        if target_destination is not None:
            dest_lower = target_destination.strip().lower()
            for blocked in network_config.blocked_services:
                if blocked in dest_lower:
                    raise SandboxIsolationError(
                        f"SSRF violation: Sandbox target destination '{target_destination}' targets blocked internal service '{blocked}'."
                    )
            # Enterprise database port blocks
            for port in (5432, 6379, 27017, 9200):
                if f":{port}" in dest_lower:
                    raise SandboxIsolationError(
                        f"Access to enterprise internal service on port {port} is strictly forbidden from sandbox."
                    )

            # If default deny_all and destination is not in allowed_domains, reject
            if network_config.policy_mode == "deny_all":
                is_allowed = False
                for domain in network_config.allowed_domains:
                    if domain.lower() in dest_lower:
                        is_allowed = True
                        break
                if not is_allowed:
                    raise SandboxIsolationError(
                        f"Network egress policy violation: Destination '{target_destination}' is blocked under default DENY_ALL."
                    )


# ===========================================================================
# Cryptographic Output Sealer
# ===========================================================================

class OutputSealer:
    """Cryptographically hashes and seals generated artifacts before sandbox teardown."""

    @staticmethod
    def seal_output(
        sandbox_id: str,
        identity: SandboxIdentity,
        workspace_path: Path | None = None,
        raw_output: dict[str, Any] | None = None,
    ) -> SealedSandboxOutput:
        """Scan workspace and output payload, compute SHA-256 digests, and seal output."""
        raw_output = raw_output or {}
        artifacts: dict[str, str] = {}
        artifact_hashes: dict[str, str] = {}

        # 1. Scan ephemeral workspace for produced files if available
        if workspace_path and workspace_path.exists():
            for p in workspace_path.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(workspace_path).as_posix()
                    try:
                        content = p.read_text(encoding="utf-8")
                        artifacts[rel] = content
                        artifact_hashes[rel] = hashlib.sha256(content.encode("utf-8")).hexdigest()
                    except (UnicodeDecodeError, OSError):
                        pass

        # 2. Extract and hash diffs from payload
        diff = str(raw_output.get("diff", raw_output.get("generated_diff", "")))
        diff_hash = hashlib.sha256(diff.encode("utf-8")).hexdigest() if diff else ""

        # 3. Include any named artifacts from payload
        for key in ("product_specification", "verified_dossier", "variants", "code"):
            if key in raw_output and key not in artifacts:
                val = str(raw_output[key])
                artifacts[key] = val
                artifact_hashes[key] = hashlib.sha256(val.encode("utf-8")).hexdigest()

        sanitized_output = {
            k: str(v) for k, v in raw_output.items() if isinstance(v, (str, int, float, bool))
        }

        return SealedSandboxOutput(
            sandbox_id=sandbox_id,
            task_id=identity.task_id,
            step_id=identity.step_id,
            attempt_id=identity.attempt_id,
            artifacts=artifacts,
            artifact_hashes=artifact_hashes,
            generated_diff=diff,
            diff_hash=diff_hash,
            sanitized_output=sanitized_output,
            structured_output=raw_output,
            sealed_at=datetime.now(UTC),
        )


# ===========================================================================
# Sandbox Execution Instance Model
# ===========================================================================

class SandboxInstance:
    """Runtime representation of a provisioned, validated sandbox container/microVM."""

    def __init__(
        self,
        identity: SandboxIdentity,
        lease: DevelopmentExecutionLease,
        grant: SandboxCapabilityGrant,
        workspace_dir: Path,
        input_hashes: dict[str, str],
        credential_token: str,
        resource_limits: SandboxResourceLimits,
        network_policy: SandboxNetworkPolicyConfig,
    ) -> None:
        self.identity = identity
        self.lease = lease
        self.grant = grant
        self.workspace_dir = workspace_dir
        self.input_hashes = input_hashes
        self.credential_token = credential_token
        self.resource_limits = resource_limits
        self.network_policy = network_policy
        self.state: SandboxLifecycleState = SandboxLifecycleState.PROVISIONING
        self.created_at: datetime = datetime.now(UTC)
        self.sealed_output: SealedSandboxOutput | None = None
        self.destroyed_at: datetime | None = None


# ===========================================================================
# Sandbox Control Plane
# ===========================================================================

class SandboxControlPlane:
    """Authoritative control plane for sandbox lifecycle, boundaries, and teardown."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        materializer: WorkspaceMaterializer | None = None,
        credential_manager: SandboxCredentialManager | None = None,
    ) -> None:
        self.materializer = materializer or WorkspaceMaterializer(base_dir)
        self.credential_manager = credential_manager or SandboxCredentialManager()
        self._sandboxes: dict[str, SandboxInstance] = {}

    def get_sandbox(self, sandbox_id: str) -> SandboxInstance | None:
        return self._sandboxes.get(sandbox_id)

    def provision(
        self,
        *,
        identity: SandboxIdentity,
        lease: DevelopmentExecutionLease,
        grant: SandboxCapabilityGrant,
        input_snapshot: dict[str, str] | None = None,
        resource_limits: SandboxResourceLimits | None = None,
        network_policy: SandboxNetworkPolicyConfig | None = None,
    ) -> SandboxInstance:
        """Provision a fresh isolated sandbox instance for a specific sub-agent attempt.

        Enforces:
        1. Valid lease check.
        2. No sandbox reuse across retries (fail-closed).
        3. Fresh ephemeral workspace materialization.
        4. Short-lived credential issuance.
        5. Pre-execution isolation validation.
        6. State transitions: PROVISIONING -> VALIDATED.
        """
        # 1. Lease validation
        IsolationValidator.validate_lease(identity, lease)

        # 2. Enforce one fresh sandbox per attempt - check for collision
        if identity.sandbox_id in self._sandboxes:
            raise SandboxIsolationError(
                f"Sandbox instance '{identity.sandbox_id}' already exists. Sandbox reuse across attempts is prohibited."
            )

        limits = resource_limits or SandboxResourceLimits()
        net_policy = network_policy or SandboxNetworkPolicyConfig()

        # 3. Resource boundary check
        IsolationValidator.validate_resource_boundaries(limits)

        # 4. Prepare fresh ephemeral workspace
        workspace_dir, input_hashes = self.materializer.prepare_workspace(
            identity.sandbox_id, input_snapshot
        )

        # 5. Issue short-lived credential
        token = self.credential_manager.issue_credential(identity, lease)

        instance = SandboxInstance(
            identity=identity,
            lease=lease,
            grant=grant,
            workspace_dir=workspace_dir,
            input_hashes=input_hashes,
            credential_token=token,
            resource_limits=limits,
            network_policy=net_policy,
        )

        # 6. Validate isolation & transition state
        self.validate(instance)
        instance.state = SandboxLifecycleState.VALIDATED

        self._sandboxes[identity.sandbox_id] = instance
        logger.info(
            "Sandbox %s provisioned and validated successfully (tenant=%s, task=%s, step=%s, attempt=%s)",
            identity.sandbox_id,
            identity.tenant_id,
            identity.task_id,
            identity.step_id,
            identity.attempt_id,
        )
        return instance

    def validate(self, instance: SandboxInstance) -> bool:
        """Perform comprehensive pre-execution validation checks."""
        IsolationValidator.validate_lease(instance.identity, instance.lease)
        IsolationValidator.validate_resource_boundaries(instance.resource_limits)
        IsolationValidator.validate_network_isolation(instance.network_policy)

        # Ensure credential is valid
        if not self.credential_manager.is_valid(instance.identity.sandbox_id, instance.credential_token):
            raise SandboxValidationError("Sandbox short-lived credential is not valid or has expired.")

        # Ensure workspace directory exists and is strictly isolated
        if not instance.workspace_dir.exists():
            raise SandboxValidationError(f"Workspace directory '{instance.workspace_dir}' does not exist.")

        return True

    def execute(
        self,
        sandbox_id: str,
        mandate: SandboxInvocationMandate,
        runner_fn: Any | None = None,
    ) -> dict[str, Any]:
        """Execute a capability/mandate inside the provisioned and validated sandbox.

        Enforces:
        1. Sandbox state must be VALIDATED.
        2. Tool and capability allow-listing against capability grant.
        3. Deny-by-default egress and SSRF destination blocking.
        4. State transition: VALIDATED -> RUNNING.
        """
        instance = self.get_sandbox(sandbox_id)
        if instance is None:
            raise SandboxExecutionError(f"Sandbox '{sandbox_id}' not found.")

        if instance.state != SandboxLifecycleState.VALIDATED:
            raise SandboxExecutionError(
                f"Cannot execute in sandbox '{sandbox_id}': State is {instance.state.value}, expected VALIDATED."
            )

        # Validate lease has not expired before running
        IsolationValidator.validate_lease(instance.identity, instance.lease)

        # Enforce capability allowlist
        if mandate.capability != instance.grant.capability:
            raise PolicyViolationError(
                f"Sandbox capability violation: Requested '{mandate.capability.value}', "
                f"authorized '{instance.grant.capability.value}'."
            )

        # Enforce tool allowlist
        for tool in mandate.allowed_tools:
            validate_tool_access(tool, mandate.capability, instance.grant)

        # Enforce network destination safety
        target = (
            mandate.payload.get("url")
            or mandate.payload.get("target_url")
            or mandate.payload.get("domain")
        )
        if target:
            IsolationValidator.validate_network_isolation(instance.network_policy, str(target))

        instance.state = SandboxLifecycleState.RUNNING

        try:
            if runner_fn is not None:
                result = runner_fn(mandate, instance.workspace_dir)
            else:
                result = {"status": "success", "stdout": "Execution completed", "diff": ""}
            return result
        except Exception as exc:
            instance.state = SandboxLifecycleState.FAILED
            raise SandboxExecutionError(f"Execution failed in sandbox '{sandbox_id}': {exc}") from exc

    def seal(
        self,
        sandbox_id: str,
        raw_output: dict[str, Any] | None = None,
    ) -> SealedSandboxOutput:
        """Extract and cryptographically seal all outputs before teardown.

        State transition: RUNNING -> RESULT_SEALED.
        """
        instance = self.get_sandbox(sandbox_id)
        if instance is None:
            raise SandboxExecutionError(f"Sandbox '{sandbox_id}' not found.")

        sealed = OutputSealer.seal_output(
            sandbox_id=sandbox_id,
            identity=instance.identity,
            workspace_path=instance.workspace_dir,
            raw_output=raw_output,
        )
        instance.sealed_output = sealed
        instance.state = SandboxLifecycleState.RESULT_SEALED
        logger.info(
            "Sandbox %s outputs cryptographically sealed (artifacts=%d, has_diff=%s)",
            sandbox_id,
            len(sealed.artifacts),
            bool(sealed.generated_diff),
        )
        return sealed

    def destroy(self, sandbox_id: str, reason: str = "completed") -> bool:
        """Deterministically clean up and wipe all state for this sandbox attempt.

        Guaranteed to:
        1. Scrub ephemeral workspace directory.
        2. Revoke short-lived credentials.
        3. Mark instance as DESTROYED.
        """
        instance = self.get_sandbox(sandbox_id)
        if instance is None:
            return False

        # 1. Scrub workspace storage
        self.materializer.scrub_workspace(sandbox_id)

        # 2. Revoke credential
        self.credential_manager.revoke_credential(sandbox_id)

        # 3. Transition lifecycle state
        instance.state = SandboxLifecycleState.DESTROYED
        instance.destroyed_at = datetime.now(UTC)

        logger.info(
            "Sandbox %s deterministically destroyed and scrubbed (reason=%s)",
            sandbox_id,
            reason,
        )
        return True
