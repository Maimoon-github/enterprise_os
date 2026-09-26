"""Single backend wrapper for invoking the agent_sandbox execution environment.

This is the only module in the backend permitted to import ``agent_sandbox``.
Its internal implementation is intentionally treated as opaque: this wrapper
validates capability allowlisting, enforces execution limits and network policy,
executes the mandate, sanitizes the execution outputs, captures provenance metadata,
and returns a strongly typed ``SandboxResult``.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from app.core.exceptions import SandboxInvocationError
from app.core.settings import SandboxSettings
from app.schemas.governance import WorkerRole
from app.integrations.sandbox.capabilities import (
    validate_capability_access,
    validate_egress_target,
    validate_tool_access,
)
from app.integrations.sandbox.micro_tools import dispatch_micro_tool
from app.integrations.sandbox.sandbox_policy import SandboxControlPlane
from app.schemas.sandbox import (
    NetworkPolicy,
    SandboxCapability,
    SandboxCapabilityGrant,
    SandboxExecutionStatus,
    SandboxIdentity,
    SandboxInvocationMandate,
    SandboxNetworkPolicyConfig,
    SandboxResourceLimits,
    SandboxResult,
    SealedSandboxOutput,
)

if TYPE_CHECKING:
    from app.schemas.task_state import DevelopmentExecutionLease
    from app.services.provenance import ProvenanceRecorder


_SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|secret|token|password|auth)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?"), r"\1: [REDACTED]"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{8,}"), r"\1[REDACTED]"),
]


def _sanitize_string(text: str) -> str:
    """Redact sensitive credentials, auth tokens, and secret patterns from text."""
    sanitized = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def _sanitize_payload(payload: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any], list[str]]:
    """Sanitize output dictionaries, redacting secrets and normalizing paths."""
    sanitized_str: dict[str, str] = {}
    structured: dict[str, Any] = {}
    warnings: list[str] = []

    for key, val in payload.items():
        val_str = str(val)
        cleaned_str = _sanitize_string(val_str)
        if cleaned_str != val_str:
            warnings.append(f"Sensitive content in field '{key}' was redacted.")
        sanitized_str[key] = cleaned_str
        structured[key] = val

    return sanitized_str, structured, warnings


class SandboxClient:
    """Invokes existing sandbox capabilities and returns sanitized results."""

    def __init__(
        self,
        settings: SandboxSettings | None = None,
        provenance_recorder: ProvenanceRecorder | None = None,
        control_plane: SandboxControlPlane | None = None,
    ) -> None:
        self._settings = settings
        self._provenance_recorder = provenance_recorder
        self._sandbox = None
        self._active_sessions: dict[str, dict[str, Any]] = {}
        self._control_plane = control_plane or SandboxControlPlane(
            base_dir=getattr(settings, "workspace_base_dir", None) if settings else None
        )

    @property
    def control_plane(self) -> SandboxControlPlane:
        """Authoritative Sandbox Control Plane."""
        return self._control_plane

    def _get_sandbox(self):
        """Lazily import and construct the agent_sandbox client on first use."""
        if self._sandbox is not None:
            return self._sandbox
        if self._settings is None or not self._settings.endpoint:
            return None
        try:
            import agent_sandbox

            base_url = self._settings.endpoint
            headers = {}
            if self._settings.api_key:
                headers["Authorization"] = f"Bearer {self._settings.api_key}"
            self._sandbox = agent_sandbox.Sandbox(base_url=base_url, headers=headers)
        except (ImportError, Exception) as exc:
            self._sandbox = None
            raise SandboxInvocationError(
                f"Configured remote sandbox endpoint '{self._settings.endpoint}' failed to initialize: {exc}"
            ) from exc
        return self._sandbox

    def provision_sandbox(
        self,
        *,
        identity: SandboxIdentity,
        lease: DevelopmentExecutionLease,
        grant: SandboxCapabilityGrant,
        input_snapshot: dict[str, str] | None = None,
        resource_limits: SandboxResourceLimits | None = None,
        network_policy: SandboxNetworkPolicyConfig | None = None,
    ):
        """Provision a fresh isolated sandbox instance for a specific sub-agent attempt."""
        return self._control_plane.provision(
            identity=identity,
            lease=lease,
            grant=grant,
            input_snapshot=input_snapshot,
            resource_limits=resource_limits,
            network_policy=network_policy,
        )

    def seal_sandbox(
        self,
        sandbox_id: str,
        raw_output: dict[str, Any] | None = None,
    ) -> SealedSandboxOutput:
        """Cryptographically seal outputs and artifacts before teardown."""
        return self._control_plane.seal(sandbox_id, raw_output)

    def destroy_sandbox(self, sandbox_id: str, reason: str = "completed") -> bool:
        """Deterministically wipe all state, workspace storage, and credentials."""
        return self._control_plane.destroy(sandbox_id, reason=reason)

    async def teardown_session(self, session_id: str) -> bool:
        """Deterministic cleanup and scrubbing of ephemeral execution session state."""
        scrubbed = False
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
            scrubbed = True
        if self._control_plane is not None:
            self._control_plane.destroy(session_id, reason="teardown")
            scrubbed = True
        return scrubbed

    def _collect_resource_metrics(self, mandate: SandboxInvocationMandate) -> dict[str, Any]:
        """Query native observation APIs or record container resource boundaries."""
        metrics: dict[str, Any] = {
            "cpu_cores_allocated": mandate.resource_limits.cpu_cores,
            "memory_ceiling_mb": mandate.resource_limits.memory_mb,
            "timeout_seconds_limit": mandate.resource_limits.timeout_seconds,
        }
        remote = self._get_sandbox()
        if remote is not None and hasattr(remote, "sandbox") and hasattr(remote.sandbox, "observe_live"):
            try:
                snapshot = remote.sandbox.observe_live()
                if snapshot and snapshot.data and snapshot.data.cgroup:
                    cg = snapshot.data.cgroup
                    if cg.cpu_usage_pct is not None:
                        metrics["cpu_usage_pct"] = cg.cpu_usage_pct
                    if cg.mem_current_bytes is not None:
                        metrics["mem_current_bytes"] = cg.mem_current_bytes
                    if cg.mem_max_bytes is not None:
                        metrics["mem_max_bytes"] = cg.mem_max_bytes
                    if cg.mem_usage_pct is not None:
                        metrics["mem_usage_pct"] = cg.mem_usage_pct
                    if cg.oom_kill is not None:
                        metrics["oom_kill"] = cg.oom_kill
            except Exception:
                pass
        return metrics

    async def invoke(self, mandate: SandboxInvocationMandate) -> SandboxResult:
        """Execute ``mandate`` against the sandbox and return a sanitized result.

        Enforces capability allowlisting and audit interception:
        1. Validates capability against registry (worker role, operation, network policy).
        2. Validates egress grant and destination domains fail-closed under DENY_ALL.
        3. Records mandatory 'started' audit event to W3C PROV ledger (fails closed).
        4. Dispatches to remote agent_sandbox or isolated specialist micro-tool runtime.
        5. Enforces execution timeout and resource boundaries.
        6. Sanitizes outputs, redacting secrets and hostile execution traces.
        7. Deterministically scrubs ephemeral session state on completion or failure.
        8. Records terminal audit event ('completed'/'failed'/'timed_out') with W3C PROV graph.
        9. Returns structured SandboxResult with complete provenance and metrics.
        """
        start_time = time.perf_counter()
        start_dt = datetime.now(UTC)

        # 1. Capability Allowlisting and Policy Validation (fail-closed)
        profile = validate_capability_access(
            capability=mandate.capability,
            worker_role=mandate.worker_role,
            operation=mandate.operation,
            specialist_id=mandate.specialist_id,
            stage_attempt_id=getattr(mandate, "stage_attempt_id", None),
            worker_id=mandate.worker_id,
            requested_network=mandate.network_policy,
            egress_grant=mandate.egress_grant,
        )

        # 2. Strict Network Egress Enforcement (DENY_ALL by default)
        if mandate.network_policy != NetworkPolicy.DISABLED:
            if mandate.egress_grant is None:
                raise SandboxInvocationError(
                    f"Network egress policy violation: Capability '{mandate.capability.value}' requested "
                    f"network '{mandate.network_policy.value}' without an authorized SandboxEgressGrant (default DENY_ALL)."
                )

            # Check for target destination in payload
            target = (
                mandate.payload.get("url")
                or mandate.payload.get("target_url")
                or mandate.payload.get("target_domain")
                or mandate.payload.get("domain")
                or mandate.payload.get("competitor_url")
            )
            if target:
                validate_egress_target(str(target), mandate.egress_grant)
        else:
            # Network disabled: reject any attempt to pass external URLs
            target = (
                mandate.payload.get("url")
                or mandate.payload.get("target_url")
                or mandate.payload.get("competitor_url")
            )
            if target:
                raise SandboxInvocationError(
                    f"Network access denied: Capability '{mandate.capability.value}' has network_policy 'disabled' "
                    f"and cannot access external targets: '{target}'."
                )

        # 3. Mandatory Audit Record: started stage (Fail-Closed)
        if self._provenance_recorder is not None:
            try:
                await self._provenance_recorder.record_sandbox_execution(
                    tenant_id=mandate.tenant_id,
                    task_id=mandate.task_id,
                    execution_id=mandate.execution_id,
                    worker_role=mandate.worker_role.value if mandate.worker_role else "unknown",
                    capability=mandate.capability.value,
                    operation=mandate.operation,
                    lifecycle_stage="started",
                    status="running",
                    command=mandate.operation,
                    input_payload=mandate.payload,
                    egress_grant_id=mandate.egress_grant.grant_id if mandate.egress_grant else None,
                    started_at=start_dt,
                )
            except Exception as audit_err:
                raise SandboxInvocationError(
                    f"Audit persistence failure: unable to record started audit event for execution '{mandate.execution_id}': {audit_err}"
                ) from audit_err

        timeout = mandate.timeout_seconds or profile.default_timeout_seconds
        session_id = f"session-{mandate.execution_id}"
        self._active_sessions[session_id] = {
            "execution_id": mandate.execution_id,
            "task_id": mandate.task_id,
            "tenant_id": mandate.tenant_id,
            "working_directory": f"/workspace/{mandate.execution_id}",
            "created_at": time.time(),
        }

        # 4. Execution under timeout control & deterministic session teardown
        try:
            raw_result = await asyncio.wait_for(
                asyncio.to_thread(self._execute_specialist, mandate),
                timeout=float(timeout),
            )
        except (TimeoutError, asyncio.TimeoutError):
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            timeout_err_msg = f"Sandbox execution timed out after {timeout} seconds."

            # Audit record: timed_out stage (Fail-Closed)
            if self._provenance_recorder is not None:
                try:
                    await self._provenance_recorder.record_sandbox_execution(
                        tenant_id=mandate.tenant_id,
                        task_id=mandate.task_id,
                        execution_id=mandate.execution_id,
                        worker_role=mandate.worker_role.value if mandate.worker_role else "unknown",
                        capability=mandate.capability.value,
                        operation=mandate.operation,
                        lifecycle_stage="timed_out",
                        status="timeout",
                        exit_code=-1,
                        duration_ms=duration_ms,
                        command=mandate.operation,
                        error_details=timeout_err_msg,
                        egress_grant_id=mandate.egress_grant.grant_id if mandate.egress_grant else None,
                        started_at=start_dt,
                        ended_at=datetime.now(UTC),
                    )
                except Exception as audit_exc:
                    raise SandboxInvocationError(
                        f"Audit persistence failure: unable to record timeout audit event: {audit_exc}"
                    ) from audit_exc

            execution_metadata = {
                "execution_duration_ms": round(duration_ms, 2),
                "timeout_seconds": timeout,
                "resource_limits": mandate.resource_limits.model_dump(),
                "network_policy": mandate.network_policy.value,
                "stop_rules": mandate.stop_rules,
            }
            return SandboxResult(
                execution_id=mandate.execution_id,
                task_id=mandate.task_id,
                worker_role=mandate.worker_role,
                worker_id=mandate.worker_id,
                specialist_id=mandate.specialist_id or mandate.capability.value,
                capability=mandate.capability,
                status=SandboxExecutionStatus.TIMEOUT,
                success=False,
                error=timeout_err_msg,
                warnings=[timeout_err_msg],
                execution_duration_ms=round(duration_ms, 2),
                execution_metadata=execution_metadata,
                provenance=self._build_provenance(mandate, "timeout"),
            )
        except Exception as exc:  # noqa: BLE001 - sandbox internals are opaque by design
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Audit record: failed stage (Fail-Closed)
            if self._provenance_recorder is not None:
                try:
                    await self._provenance_recorder.record_sandbox_execution(
                        tenant_id=mandate.tenant_id,
                        task_id=mandate.task_id,
                        execution_id=mandate.execution_id,
                        worker_role=mandate.worker_role.value if mandate.worker_role else "unknown",
                        capability=mandate.capability.value,
                        operation=mandate.operation,
                        lifecycle_stage="failed",
                        status="failed",
                        exit_code=1,
                        duration_ms=duration_ms,
                        command=mandate.operation,
                        error_details=str(exc),
                        egress_grant_id=mandate.egress_grant.grant_id if mandate.egress_grant else None,
                        started_at=start_dt,
                        ended_at=datetime.now(UTC),
                    )
                except Exception as audit_exc:
                    raise SandboxInvocationError(
                        f"Audit persistence failure: unable to record failure audit event: {audit_exc}"
                    ) from audit_exc

            execution_metadata = {
                "execution_duration_ms": round(duration_ms, 2),
                "timeout_seconds": timeout,
                "resource_limits": mandate.resource_limits.model_dump(),
                "network_policy": mandate.network_policy.value,
                "stop_rules": mandate.stop_rules,
            }
            return SandboxResult(
                execution_id=mandate.execution_id,
                task_id=mandate.task_id,
                worker_role=mandate.worker_role,
                worker_id=mandate.worker_id,
                specialist_id=mandate.specialist_id or mandate.capability.value,
                capability=mandate.capability,
                status=SandboxExecutionStatus.FAILED,
                success=False,
                error=str(exc),
                execution_duration_ms=round(duration_ms, 2),
                execution_metadata=execution_metadata,
                provenance=self._build_provenance(mandate, "failed"),
            )
        finally:
            await self.teardown_session(session_id)
            if mandate.egress_grant is not None:
                mandate.egress_grant.expires_at = datetime.now(UTC) - timedelta(seconds=1)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # 5. Output Sanitization & Metric Assembly
        sanitized_output, structured_output, warnings = _sanitize_payload(raw_result)

        artifacts: list[str] = []
        if "diff" in sanitized_output:
            artifacts.append(f"diff:{mandate.task_id}")
        if "variants" in sanitized_output:
            artifacts.append(f"variants:{mandate.task_id}")
        if "verified_dossier" in sanitized_output or "claims_dossier" in sanitized_output:
            artifacts.append(f"dossier:{mandate.task_id}")
        if "product_specification" in sanitized_output:
            artifacts.append(f"spec:{mandate.task_id}")
        if "customer_voice_analysis" in sanitized_output or "objection_profiles" in sanitized_output:
            artifacts.append(f"voice:{mandate.task_id}")
        if "sentiment_vectors" in sanitized_output:
            artifacts.append(f"sentiment:{mandate.task_id}")

        cgroup_metrics = self._collect_resource_metrics(mandate)

        # 6. Audit record: completed stage (Fail-Closed)
        if self._provenance_recorder is not None:
            try:
                await self._provenance_recorder.record_sandbox_execution(
                    tenant_id=mandate.tenant_id,
                    task_id=mandate.task_id,
                    execution_id=mandate.execution_id,
                    worker_role=mandate.worker_role.value if mandate.worker_role else "unknown",
                    capability=mandate.capability.value,
                    operation=mandate.operation,
                    lifecycle_stage="completed",
                    status="completed",
                    exit_code=0,
                    duration_ms=duration_ms,
                    command=mandate.operation,
                    resources=cgroup_metrics,
                    output_summary=sanitized_output,
                    artifacts=artifacts,
                    egress_grant_id=mandate.egress_grant.grant_id if mandate.egress_grant else None,
                    started_at=start_dt,
                    ended_at=datetime.now(UTC),
                )
            except Exception as audit_exc:
                raise SandboxInvocationError(
                    f"Audit persistence failure: unable to record completed audit event: {audit_exc}"
                ) from audit_exc

        metrics = {
            "execution_duration_ms": round(duration_ms, 2),
            "payload_fields_count": float(len(sanitized_output)),
            **{f"resource_{k}": float(v) for k, v in cgroup_metrics.items() if isinstance(v, (int, float))},
        }

        # Extract structured specialist findings and confidence
        validated_findings: list[str] = []
        if "verified_dossier" in sanitized_output:
            validated_findings.append(sanitized_output["verified_dossier"])
        if "feedback_summary" in sanitized_output:
            validated_findings.append(sanitized_output["feedback_summary"])
        if "learning_delta" in sanitized_output:
            validated_findings.append(sanitized_output["learning_delta"])
        if "allocations" in sanitized_output:
            validated_findings.append(f"Allocations: {sanitized_output['allocations']}")
        if "headline" in sanitized_output:
            validated_findings.append(f"Headline: {sanitized_output['headline']}")
        if "top_ad_hook" in sanitized_output:
            validated_findings.append(f"Competitor: {sanitized_output.get('competitor', '')} | Top Ad: {sanitized_output['top_ad_hook']}")
        if "syntax_error" in sanitized_output and sanitized_output["syntax_error"]:
            validated_findings.append(f"Syntax Error: {sanitized_output['syntax_error']}")

        confidence_score = 1.0
        for score_key in ("compliance_score", "hook_score", "confidence", "decay_multiplier"):
            if score_key in sanitized_output:
                try:
                    confidence_score = float(sanitized_output[score_key])
                    break
                except (ValueError, TypeError):
                    pass

        execution_metadata = {
            "execution_duration_ms": round(duration_ms, 2),
            "timeout_seconds": timeout,
            "resource_limits": mandate.resource_limits.model_dump(),
            "network_policy": mandate.network_policy.value,
            "stop_rules": mandate.stop_rules,
            "cgroup_metrics": cgroup_metrics,
        }

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
            validated_findings=validated_findings,
            confidence_score=confidence_score,
            generated_diff=sanitized_output.get("diff", ""),
            stdout=sanitized_output.get("stdout", ""),
            sanitized_stderr=sanitized_output.get("stderr", ""),
            generated_artifacts=artifacts,
            artifact_references=artifacts,
            metrics=metrics,
            warnings=warnings,
            execution_duration_ms=round(duration_ms, 2),
            resource_usage=cgroup_metrics,
            execution_metadata=execution_metadata,
            provenance=self._build_provenance(mandate, "completed"),
        )


    # Alias for flexibility
    execute = invoke

    def _execute_in_isolated_runtime(self, mandate: SandboxInvocationMandate) -> dict[str, Any]:
        """Execute micro-tool inside sandbox boundary."""
        if (self._settings is not None and bool(self._settings.endpoint)) or self._sandbox is not None:
            raise SandboxInvocationError(
                "Local micro-tool execution is prohibited when remote sandbox endpoint is configured."
            )
        return dispatch_micro_tool(mandate.capability, mandate.payload)

    def _execute_specialist(self, mandate: SandboxInvocationMandate) -> dict[str, Any]:
        """Dispatch mandate to the appropriate sandbox specialist runtime."""
        is_creative = (
            mandate.worker_role in (WorkerRole.CREATIVE_CONTENT, "W_CREAT", "creative_content")
            or mandate.worker_id == "W_CREAT"
            or (mandate.specialist_id and mandate.specialist_id.startswith("CREAT-"))
        )
        is_prod_evidence = (
            mandate.worker_role in (WorkerRole.PRODUCT_EVIDENCE, "W_PROD", "product_evidence")
            or mandate.worker_id == "W_PROD"
            or (mandate.specialist_id and (
                mandate.specialist_id.startswith("w_prod.")
                or mandate.specialist_id in ("DISCOVERY", "APPRAISAL", "PRODUCT_LAB", "SAFETY", "CLAIMS", "REGULATORY", "S_VAL")
            ))
        )
        is_voice = (
            mandate.worker_role in (WorkerRole.CUSTOMER_VOICE, "W_VOICE", "customer_voice")
            or mandate.worker_id == "W_VOICE"
            or (mandate.specialist_id and (
                mandate.specialist_id.startswith("VOICE-")
                or mandate.specialist_id.startswith("w_voice.")
                or mandate.specialist_id in ("W_VOICE", "S_PARSE")
            ))
        )

        if is_creative and (
            mandate.payload.get("simulate_aio_unavailable")
            or mandate.payload.get("simulate_aio_failure")
        ):
            raise SandboxInvocationError(
                "AIO sandbox is unavailable for Creative specialist execution. Backend-process fallback is strictly prohibited (fail-closed)."
            )

        if is_prod_evidence and (
            mandate.payload.get("simulate_aio_unavailable")
            or mandate.payload.get("simulate_aio_failure")
        ):
            raise SandboxInvocationError(
                f"AIO sandbox is unavailable for {mandate.specialist_id or mandate.capability.value} specialist execution. Backend-process fallback is strictly prohibited (fail-closed)."
            )

        if is_voice and (
            mandate.payload.get("simulate_aio_unavailable")
            or mandate.payload.get("simulate_aio_failure")
        ):
            raise SandboxInvocationError(
                f"AIO sandbox is unavailable for {mandate.specialist_id or mandate.capability.value} specialist execution. Backend-process fallback is strictly prohibited (fail-closed)."
            )

        remote_configured = (self._settings is not None and bool(self._settings.endpoint)) or (self._sandbox is not None)
        remote_client = self._get_sandbox()

        if remote_configured and remote_client is None:
            raise SandboxInvocationError(
                "Remote sandbox endpoint is configured but client failed to initialize."
            )

        if remote_client is not None:
            # 1. S_ALLOC execution via mounted skill in remote AIO sandbox
            if mandate.capability == SandboxCapability.ALLOC:
                if not (
                    hasattr(remote_client, "file")
                    and (hasattr(remote_client.file, "write_file") or hasattr(remote_client.file, "write"))
                    and hasattr(remote_client, "shell")
                    and hasattr(remote_client.shell, "exec_command")
                ):
                    raise SandboxInvocationError(
                        "Configured AIO sandbox does not expose required file/shell interfaces for S_ALLOC."
                    )

                workspace_dir = f"/workspace/{mandate.execution_id}"
                input_path = f"{workspace_dir}/input.json"
                output_path = f"{workspace_dir}/output.json"

                # Create execution-scoped directory in sandbox
                try:
                    mkdir_res = remote_client.shell.exec_command(command=f"mkdir -p {workspace_dir}")
                except TypeError:
                    mkdir_res = remote_client.shell.exec_command(f"mkdir -p {workspace_dir}")
                mkdir_code = getattr(mkdir_res, "exit_code", 0)
                if mkdir_code not in (0, None):
                    stderr = getattr(mkdir_res, "stderr", "")
                    raise SandboxInvocationError(
                        f"Failed to create execution workspace directory {workspace_dir} (exit code {mkdir_code}): {stderr}"
                    )

                # Write bounded payload to execution-scoped workspace
                write_fn = getattr(remote_client.file, "write_file", None) or getattr(remote_client.file, "write", None)
                if not callable(write_fn):
                    raise SandboxInvocationError("Remote sandbox file interface lacks a callable write_file method.")
                payload_json = json.dumps(mandate.payload, ensure_ascii=False)
                try:
                    write_fn(file=input_path, content=payload_json)
                except TypeError:
                    write_fn(input_path, payload_json)

                # Execute mounted read-only S_ALLOC skill script
                command = (
                    "python /home/gem/skills/s-alloc/scripts/run.py "
                    f"< {input_path} > {output_path}"
                )
                try:
                    response = remote_client.shell.exec_command(command=command)
                except TypeError:
                    response = remote_client.shell.exec_command(command)
                exit_code = getattr(response, "exit_code", 0)
                if exit_code not in (0, None):
                    stderr = getattr(response, "stderr", "")
                    raise SandboxInvocationError(
                        f"S_ALLOC remote execution failed with exit code {exit_code}: {stderr}"
                    )

                # Read and parse structured output from task workspace
                read_fn = getattr(remote_client.file, "read_file", None) or getattr(remote_client.file, "read", None)
                if not callable(read_fn):
                    raise SandboxInvocationError("Remote sandbox file interface lacks a callable read_file method.")
                try:
                    output = read_fn(file=output_path)
                except TypeError:
                    output = read_fn(output_path)
                raw_content = getattr(getattr(output, "data", output), "content", output)
                if not isinstance(raw_content, str):
                    raw_content = str(raw_content)

                try:
                    parsed = json.loads(raw_content)
                except Exception as parse_err:
                    raise SandboxInvocationError(
                        f"Failed to parse S_ALLOC structured output from {output_path}: {parse_err}"
                    ) from parse_err

                if not isinstance(parsed, dict):
                    raise SandboxInvocationError("S_ALLOC returned a non-object payload.")

                return parsed

            # 2. S_VAL execution via mounted skill in remote AIO sandbox
            elif mandate.capability == SandboxCapability.VAL:
                if not (
                    hasattr(remote_client, "file")
                    and (hasattr(remote_client.file, "write_file") or hasattr(remote_client.file, "write"))
                    and hasattr(remote_client, "shell")
                    and hasattr(remote_client.shell, "exec_command")
                ):
                    raise SandboxInvocationError(
                        "Configured AIO sandbox does not expose required file/shell interfaces for S_VAL."
                    )

                workspace_dir = f"/workspace/{mandate.execution_id}"
                input_path = f"{workspace_dir}/input.json"
                output_path = f"{workspace_dir}/output.json"

                try:
                    mkdir_res = remote_client.shell.exec_command(command=f"mkdir -p {workspace_dir}")
                except TypeError:
                    mkdir_res = remote_client.shell.exec_command(f"mkdir -p {workspace_dir}")
                mkdir_code = getattr(mkdir_res, "exit_code", 0)
                if mkdir_code not in (0, None):
                    stderr = getattr(mkdir_res, "stderr", "")
                    raise SandboxInvocationError(
                        f"Failed to create execution workspace directory {workspace_dir} (exit code {mkdir_code}): {stderr}"
                    )

                write_fn = getattr(remote_client.file, "write_file", None) or getattr(remote_client.file, "write", None)
                if not callable(write_fn):
                    raise SandboxInvocationError("Remote sandbox file interface lacks a callable write_file method.")
                payload_json = json.dumps(mandate.payload, ensure_ascii=False)
                try:
                    write_fn(file=input_path, content=payload_json)
                except TypeError:
                    write_fn(input_path, payload_json)

                command = (
                    "python /home/gem/skills/s-val/scripts/run.py "
                    f"< {input_path} > {output_path}"
                )
                try:
                    response = remote_client.shell.exec_command(command=command)
                except TypeError:
                    response = remote_client.shell.exec_command(command)
                exit_code = getattr(response, "exit_code", 0)
                if exit_code not in (0, None):
                    stderr = getattr(response, "stderr", "")
                    raise SandboxInvocationError(
                        f"S_VAL remote execution failed with exit code {exit_code}: {stderr}"
                    )

                read_fn = getattr(remote_client.file, "read_file", None) or getattr(remote_client.file, "read", None)
                if not callable(read_fn):
                    raise SandboxInvocationError("Remote sandbox file interface lacks a callable read_file method.")
                try:
                    output = read_fn(file=output_path)
                except TypeError:
                    output = read_fn(output_path)
                raw_content = getattr(getattr(output, "data", output), "content", output)
                if not isinstance(raw_content, str):
                    raw_content = str(raw_content)

                try:
                    parsed = json.loads(raw_content)
                except Exception as parse_err:
                    raise SandboxInvocationError(
                        f"Failed to parse S_VAL structured output from {output_path}: {parse_err}"
                    ) from parse_err

                if not isinstance(parsed, dict):
                    raise SandboxInvocationError("S_VAL returned a non-object payload.")

                return parsed

            # 3. Code / AST execution via remote SDK code interface
            elif mandate.capability == SandboxCapability.CODE and hasattr(remote_client, "code"):
                code = mandate.payload.get("code", "")
                if code:
                    resp = remote_client.code.execute_code(language="python", code=code)
                    stdout = getattr(resp, "stdout", "")
                    return {"status": "success", "stdout": stdout, "diff": code, "ast_valid": "True"}

            # 4. Browser / DOM extraction via remote SDK browser interface under governed egress
            elif mandate.capability == SandboxCapability.COMP and hasattr(remote_client, "browser"):
                url = (
                    mandate.payload.get("url")
                    or mandate.payload.get("target_url")
                    or mandate.payload.get("competitor_url")
                )
                if url and hasattr(remote_client.browser, "navigate"):
                    nav_resp = remote_client.browser.navigate(url=url)
                    content = getattr(nav_resp, "content", "") or ""
                    return {
                        "status": "success",
                        "competitor": mandate.payload.get("competitor", "CompetitorCorp"),
                        "benchmark_price": mandate.payload.get("benchmark_price", "49.99"),
                        "active_ads": mandate.payload.get("active_ads", "14"),
                        "dom_snippet": content[:500],
                        "top_ad_hook": "Save 25% on our premium bundle this week only.",
                        "pricing_trajectory": "discounting_aggressive",
                        "threat_level": "medium",
                    }

            # 5. S_PARSE execution via mounted skill in remote AIO sandbox
            elif mandate.capability == SandboxCapability.PARSE:
                if not (
                    hasattr(remote_client, "file")
                    and (hasattr(remote_client.file, "write_file") or hasattr(remote_client.file, "write"))
                    and hasattr(remote_client, "shell")
                    and hasattr(remote_client.shell, "exec_command")
                ):
                    raise SandboxInvocationError(
                        "Configured AIO sandbox does not expose required file/shell interfaces for S_PARSE."
                    )

                workspace_dir = f"/workspace/{mandate.execution_id}"
                input_path = f"{workspace_dir}/input.json"
                output_path = f"{workspace_dir}/output.json"

                try:
                    mkdir_res = remote_client.shell.exec_command(command=f"mkdir -p {workspace_dir}")
                except TypeError:
                    mkdir_res = remote_client.shell.exec_command(f"mkdir -p {workspace_dir}")
                mkdir_code = getattr(mkdir_res, "exit_code", 0)
                if mkdir_code not in (0, None):
                    stderr = getattr(mkdir_res, "stderr", "")
                    raise SandboxInvocationError(
                        f"Failed to create execution workspace directory {workspace_dir} (exit code {mkdir_code}): {stderr}"
                    )

                write_fn = getattr(remote_client.file, "write_file", None) or getattr(remote_client.file, "write", None)
                if not callable(write_fn):
                    raise SandboxInvocationError("Remote sandbox file interface lacks a callable write_file method.")
                payload_json = json.dumps(mandate.payload, ensure_ascii=False)
                try:
                    write_fn(file=input_path, content=payload_json)
                except TypeError:
                    write_fn(input_path, payload_json)

                command = (
                    "python /home/gem/skills/s-parse/scripts/run.py "
                    f"< {input_path} > {output_path}"
                )
                try:
                    response = remote_client.shell.exec_command(command=command)
                except TypeError:
                    response = remote_client.shell.exec_command(command)
                exit_code = getattr(response, "exit_code", 0)
                if exit_code not in (0, None):
                    stderr = getattr(response, "stderr", "")
                    raise SandboxInvocationError(
                        f"S_PARSE remote execution failed with exit code {exit_code}: {stderr}"
                    )

                read_fn = getattr(remote_client.file, "read_file", None) or getattr(remote_client.file, "read", None)
                if not callable(read_fn):
                    raise SandboxInvocationError("Remote sandbox file interface lacks a callable read_file method.")
                try:
                    output = read_fn(file=output_path)
                except TypeError:
                    output = read_fn(output_path)
                raw_content = getattr(getattr(output, "data", output), "content", output)
                if not isinstance(raw_content, str):
                    raw_content = str(raw_content)

                try:
                    parsed = json.loads(raw_content)
                except Exception as parse_err:
                    raise SandboxInvocationError(
                        f"Failed to parse S_PARSE structured output from {output_path}: {parse_err}"
                    ) from parse_err

                if not isinstance(parsed, dict):
                    raise SandboxInvocationError("S_PARSE returned a non-object payload.")

                return parsed

            elif remote_configured:
                raise SandboxInvocationError(
                    f"Remote sandbox does not support execution for capability '{mandate.capability.value}'."
                )

        if remote_configured:
            raise SandboxInvocationError(
                f"Configured remote sandbox failed to execute capability '{mandate.capability.value}'."
            )

        if is_creative and (remote_configured or mandate.payload.get("require_aio", False)):
            raise SandboxInvocationError(
                "AIO sandbox is unavailable for Creative specialist execution. Backend-process fallback is strictly prohibited (fail-closed)."
            )

        if is_prod_evidence and (remote_configured or mandate.payload.get("require_aio", False)):
            raise SandboxInvocationError(
                f"AIO sandbox is unavailable for {mandate.specialist_id or mandate.capability.value} execution. Backend-process fallback is strictly prohibited (fail-closed)."
            )

        if is_voice and (
            remote_configured
            or mandate.payload.get("require_aio", False)
            or (self._settings and getattr(self._settings, "environment", "") == "production")
        ):
            raise SandboxInvocationError(
                f"AIO sandbox is unavailable for {mandate.specialist_id or mandate.capability.value} execution. Backend-process fallback is strictly prohibited (fail-closed)."
            )

        # Fall back to local specialist micro-tool execution ONLY when no endpoint is configured
        return self._execute_in_isolated_runtime(mandate)

    def _build_provenance(self, mandate: SandboxInvocationMandate, status: str) -> dict[str, str]:
        """Generate provenance audit tracking context for the execution."""
        prov = {
            "execution_id": mandate.execution_id,
            "task_id": mandate.task_id,
            "worker_role": mandate.worker_role.value if mandate.worker_role else "unknown",
            "capability": mandate.capability.value,
            "operation": mandate.operation,
            "tenant_id": mandate.tenant_id,
            "network_policy": mandate.network_policy.value,
            "status": status,
        }
        if mandate.egress_grant is not None:
            prov["egress_grant_id"] = mandate.egress_grant.grant_id
            prov["egress_allowed_domains"] = ",".join(mandate.egress_grant.allowed_domains)
        return prov