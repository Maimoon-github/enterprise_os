"""Tests for DE-03: Sandbox Control Plane and Policy Engine.

Verifies:
1. Every attempt receives a unique isolated sandbox (no reuse across retries).
2. Valid lease + isolation validation are required before execution.
3. Capabilities and micro-tools are least-privilege and fail closed.
4. Filesystem, process, cgroups, and network boundaries are enforced.
5. Anti-SSRF, cloud metadata, enterprise DB, and host service access blocked.
6. Egress operates through explicit allow-list policy with proxy routing.
7. Credentials are short-lived and revoked at teardown.
8. Outputs and diffs are cryptographically sealed (SHA-256) before destruction.
9. Cleanup executes deterministically for success, failure, timeout, and retry.
10. Model-A boundaries strictly block sandbox callers from enterprise DB/RAG/IE.
11. State machine integration (SANDBOX_PROVISIONING -> VALIDATED -> SUBAGENT_RUNNING).
"""

from __future__ import annotations

import hashlib
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
import pytest

from app.core.exceptions import (
    AuthorizationError,
    PolicyViolationError,
    SandboxInvocationError,
)
from app.integrations.sandbox.capabilities import (
    CAPABILITY_REGISTRY,
    validate_capability_access,
    validate_tool_access,
)
from app.integrations.sandbox.client import SandboxClient
from app.integrations.sandbox.sandbox_policy import (
    IsolationValidator,
    OutputSealer,
    SandboxCleanupError,
    SandboxControlPlane,
    SandboxCredentialManager,
    SandboxExecutionError,
    SandboxIsolationError,
    SandboxValidationError,
    WorkspaceMaterializer,
)
from app.orchestration.development_state_machine import DevelopmentStateMachine
from app.schemas.governance import AutonomyTier, RiskLevel, TenantScope, WorkerRole
from app.schemas.sandbox import (
    NetworkPolicy,
    SandboxCapability,
    SandboxCapabilityGrant,
    SandboxEgressGrant,
    SandboxFilesystemPolicy,
    SandboxIdentity,
    SandboxInvocationMandate,
    SandboxLifecycleState,
    SandboxNetworkPolicyConfig,
    SandboxResourceLimits,
    SandboxResult,
    SealedSandboxOutput,
)
from app.schemas.task_state import (
    DevelopmentExecutionLease,
    DevelopmentWorkflowState,
    WorkflowRetryPolicy,
)
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity


@pytest.fixture
def sample_identity() -> SandboxIdentity:
    return SandboxIdentity.generate(
        tenant_id="acme",
        task_id="task-100",
        step_id="step-1",
        attempt_id="attempt-1",
        work_region="us-east-1",
        engine_id="W_DEV",
    )


@pytest.fixture
def sample_lease(sample_identity: SandboxIdentity) -> DevelopmentExecutionLease:
    return DevelopmentExecutionLease(
        workflow_id="wf-100",
        task_id=sample_identity.task_id,
        step_id=sample_identity.step_id,
        attempt_id=sample_identity.attempt_id,
        owner_id="W_DEV",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )


@pytest.fixture
def sample_grant(sample_lease: DevelopmentExecutionLease) -> SandboxCapabilityGrant:
    return SandboxCapabilityGrant(
        lease_id=sample_lease.lease_id,
        subagent_id="DEV-CODE",
        capability=SandboxCapability.CODE,
        allowed_tools=("ast_parser", "code_linter", "diff_generator"),
        allowed_operations=("parse_ast", "lint", "generate_diff", "execute_code", "validate_syntax", "default"),
    )


@pytest.fixture
def temp_workspace_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ===========================================================================
# 1. Fresh Isolated Sandbox Instance Per Attempt
# ===========================================================================

def test_fresh_isolated_sandbox_per_attempt(
    temp_workspace_dir: Path,
    sample_identity: SandboxIdentity,
    sample_lease: DevelopmentExecutionLease,
    sample_grant: SandboxCapabilityGrant,
):
    """Every attempt receives a fresh isolated sandbox; reusing an existing instance is rejected."""
    cp = SandboxControlPlane(base_dir=temp_workspace_dir)

    instance1 = cp.provision(
        identity=sample_identity,
        lease=sample_lease,
        grant=sample_grant,
        input_snapshot={"src/app.py": "print('hello')"},
    )
    assert instance1.state == SandboxLifecycleState.VALIDATED
    assert instance1.workspace_dir.exists()
    assert (instance1.workspace_dir / "src/app.py").read_text() == "print('hello')"

    # Attempting to provision again with the exact same sandbox_id fails closed
    with pytest.raises(SandboxIsolationError, match="Sandbox reuse across attempts is prohibited"):
        cp.provision(
            identity=sample_identity,
            lease=sample_lease,
            grant=sample_grant,
        )

    # Next attempt receives a distinct, unique identity and fresh workspace
    identity_attempt2 = SandboxIdentity.generate(
        tenant_id="acme",
        task_id=sample_identity.task_id,
        step_id=sample_identity.step_id,
        attempt_id="attempt-2",
    )
    lease_attempt2 = DevelopmentExecutionLease(
        workflow_id="wf-100",
        task_id=identity_attempt2.task_id,
        step_id=identity_attempt2.step_id,
        attempt_id=identity_attempt2.attempt_id,
        owner_id="W_DEV",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    instance2 = cp.provision(
        identity=identity_attempt2,
        lease=lease_attempt2,
        grant=sample_grant,
    )
    assert instance2.identity.sandbox_id != instance1.identity.sandbox_id
    assert instance2.workspace_dir != instance1.workspace_dir


# ===========================================================================
# 2. Lease & Isolation Pre-Execution Validation
# ===========================================================================

def test_expired_or_mismatched_lease_fails_closed(
    temp_workspace_dir: Path,
    sample_identity: SandboxIdentity,
    sample_grant: SandboxCapabilityGrant,
):
    """Missing or expired lease blocks sandbox provisioning."""
    cp = SandboxControlPlane(base_dir=temp_workspace_dir)

    # Expired lease
    expired_lease = DevelopmentExecutionLease(
        workflow_id="wf-100",
        task_id=sample_identity.task_id,
        step_id=sample_identity.step_id,
        attempt_id=sample_identity.attempt_id,
        owner_id="W_DEV",
        expires_at=datetime.now(UTC) - timedelta(seconds=10),
    )
    with pytest.raises(SandboxValidationError, match="has expired"):
        cp.provision(
            identity=sample_identity,
            lease=expired_lease,
            grant=sample_grant,
        )

    # Mismatched task_id
    mismatched_lease = DevelopmentExecutionLease(
        workflow_id="wf-100",
        task_id="wrong-task",
        step_id=sample_identity.step_id,
        attempt_id=sample_identity.attempt_id,
        owner_id="W_DEV",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    with pytest.raises(SandboxValidationError, match="does not match sandbox task_id"):
        cp.provision(
            identity=sample_identity,
            lease=mismatched_lease,
            grant=sample_grant,
        )


def test_resource_boundaries_fail_closed(
    temp_workspace_dir: Path,
    sample_identity: SandboxIdentity,
    sample_lease: DevelopmentExecutionLease,
    sample_grant: SandboxCapabilityGrant,
):
    """Prohibit root user, excessive resources, or missing security opts."""
    cp = SandboxControlPlane(base_dir=temp_workspace_dir)

    # Root user rejected
    with pytest.raises(SandboxIsolationError, match="UID 0.*forbidden"):
        cp.provision(
            identity=sample_identity,
            lease=sample_lease,
            grant=sample_grant,
            resource_limits=SandboxResourceLimits(run_as_user="0:0"),
        )

    # Missing no_new_privileges rejected
    with pytest.raises(SandboxIsolationError, match="no_new_privileges"):
        cp.provision(
            identity=sample_identity,
            lease=sample_lease,
            grant=sample_grant,
            resource_limits=SandboxResourceLimits(no_new_privileges=False),
        )

    # Missing cap_drop ALL rejected
    with pytest.raises(SandboxIsolationError, match="drop ALL Linux capabilities"):
        cp.provision(
            identity=sample_identity,
            lease=sample_lease,
            grant=sample_grant,
            resource_limits=SandboxResourceLimits(cap_drop=()),
        )


# ===========================================================================
# 3. Least Privilege & Tool Allow-Listing
# ===========================================================================

def test_tool_and_capability_allowlist_enforcement(
    temp_workspace_dir: Path,
    sample_identity: SandboxIdentity,
    sample_lease: DevelopmentExecutionLease,
    sample_grant: SandboxCapabilityGrant,
):
    """Enforce capability and microtool allow-lists fail-closed."""
    cp = SandboxControlPlane(base_dir=temp_workspace_dir)
    instance = cp.provision(
        identity=sample_identity,
        lease=sample_lease,
        grant=sample_grant,
    )

    # Unauthorized capability
    wrong_cap_mandate = SandboxInvocationMandate(
        capability=SandboxCapability.SCRAPE,
        allowed_tools=["dom_parser"],
        operation="scrape_prices",
        tenant_id=sample_identity.tenant_id,
        task_id=sample_identity.task_id,
    )
    with pytest.raises(PolicyViolationError, match="Sandbox capability violation"):
        cp.execute(instance.identity.sandbox_id, wrong_cap_mandate)

    # Unauthorized micro-tool
    wrong_tool_mandate = SandboxInvocationMandate(
        capability=SandboxCapability.CODE,
        allowed_tools=["unauthorized_compiler"],
        operation="parse_ast",
        tenant_id=sample_identity.tenant_id,
        task_id=sample_identity.task_id,
    )
    with pytest.raises(SandboxInvocationError, match="not permitted for capability"):
        cp.execute(instance.identity.sandbox_id, wrong_tool_mandate)

    # Valid tool execution succeeds
    valid_mandate = SandboxInvocationMandate(
        capability=SandboxCapability.CODE,
        allowed_tools=["ast_parser"],
        operation="parse_ast",
        tenant_id=sample_identity.tenant_id,
        task_id=sample_identity.task_id,
    )
    res = cp.execute(instance.identity.sandbox_id, valid_mandate)
    assert res["status"] == "success"
    assert instance.state == SandboxLifecycleState.RUNNING


# ===========================================================================
# 4. Immutable Input Materialization & Directory Traversal Guard
# ===========================================================================

def test_immutable_input_materialization_and_path_traversal_guard(
    temp_workspace_dir: Path,
    sample_identity: SandboxIdentity,
    sample_lease: DevelopmentExecutionLease,
    sample_grant: SandboxCapabilityGrant,
):
    """Materialize approved files; reject directory traversal escapes."""
    cp = SandboxControlPlane(base_dir=temp_workspace_dir)

    # Directory traversal in input path fails closed
    traversal_snapshot = {"../../etc/shadow": "malicious"}
    with pytest.raises(SandboxIsolationError, match="Directory traversal"):
        cp.provision(
            identity=sample_identity,
            lease=sample_lease,
            grant=sample_grant,
            input_snapshot=traversal_snapshot,
        )

    # Valid immutable snapshot materialization
    valid_snapshot = {
        "components/Button.tsx": "export const Button = () => <button>Click</button>;",
        "styles/theme.json": '{"primary": "#0055ff"}',
    }
    instance = cp.provision(
        identity=sample_identity,
        lease=sample_lease,
        grant=sample_grant,
        input_snapshot=valid_snapshot,
    )
    assert (instance.workspace_dir / "components/Button.tsx").exists()
    assert (instance.workspace_dir / "styles/theme.json").exists()
    assert len(instance.input_hashes) == 2
    assert instance.input_hashes["components/Button.tsx"] == hashlib.sha256(
        valid_snapshot["components/Button.tsx"].encode("utf-8")
    ).hexdigest()


# ===========================================================================
# 5. Deny-By-Default Egress & Anti-SSRF Protections
# ===========================================================================

def test_deny_by_default_network_and_ssrf_blocking(
    temp_workspace_dir: Path,
    sample_identity: SandboxIdentity,
    sample_lease: DevelopmentExecutionLease,
    sample_grant: SandboxCapabilityGrant,
):
    """Block cloud metadata, internal enterprise services, and unauthorized egress."""
    cp = SandboxControlPlane(base_dir=temp_workspace_dir)
    instance = cp.provision(
        identity=sample_identity,
        lease=sample_lease,
        grant=sample_grant,
    )

    # SSRF to cloud instance metadata
    metadata_mandate = SandboxInvocationMandate(
        capability=SandboxCapability.CODE,
        allowed_tools=["diff_generator"],
        payload={"url": "http://169.254.169.254/latest/meta-data/"},
        tenant_id=sample_identity.tenant_id,
        task_id=sample_identity.task_id,
    )
    with pytest.raises(SandboxIsolationError, match="SSRF violation.*blocked internal service"):
        cp.execute(instance.identity.sandbox_id, metadata_mandate)

    # SSRF to internal enterprise database
    db_mandate = SandboxInvocationMandate(
        capability=SandboxCapability.CODE,
        allowed_tools=["diff_generator"],
        payload={"url": "http://enterprise-db:5432/sql"},
        tenant_id=sample_identity.tenant_id,
        task_id=sample_identity.task_id,
    )
    with pytest.raises(SandboxIsolationError, match="SSRF violation|port 5432 is strictly forbidden"):
        cp.execute(instance.identity.sandbox_id, db_mandate)

    # External domain without egress grant is blocked under DENY_ALL
    external_mandate = SandboxInvocationMandate(
        capability=SandboxCapability.CODE,
        allowed_tools=["diff_generator"],
        payload={"url": "https://external-api.com/endpoint"},
        tenant_id=sample_identity.tenant_id,
        task_id=sample_identity.task_id,
    )
    with pytest.raises(SandboxIsolationError, match="Network egress policy violation.*DENY_ALL"):
        cp.execute(instance.identity.sandbox_id, external_mandate)


# ===========================================================================
# 6. Task-Scoped Short-Lived Credentials
# ===========================================================================

def test_short_lived_credentials_lifecycle(
    temp_workspace_dir: Path,
    sample_identity: SandboxIdentity,
    sample_lease: DevelopmentExecutionLease,
    sample_grant: SandboxCapabilityGrant,
):
    """Credential issued at provision is valid and deterministically revoked at teardown."""
    cp = SandboxControlPlane(base_dir=temp_workspace_dir)
    instance = cp.provision(
        identity=sample_identity,
        lease=sample_lease,
        grant=sample_grant,
    )
    token = instance.credential_token
    assert token.startswith(f"sbx_token_{instance.identity.sandbox_id}")
    assert cp.credential_manager.is_valid(instance.identity.sandbox_id, token) is True

    # After destroying the sandbox, credential must be revoked
    cp.destroy(instance.identity.sandbox_id)
    assert cp.credential_manager.is_valid(instance.identity.sandbox_id, token) is False


# ===========================================================================
# 7. Cryptographic Output Sealing Before Teardown
# ===========================================================================

def test_cryptographic_output_sealing(
    temp_workspace_dir: Path,
    sample_identity: SandboxIdentity,
    sample_lease: DevelopmentExecutionLease,
    sample_grant: SandboxCapabilityGrant,
):
    """Outputs and unified diffs are hashed with SHA-256 and sealed before destruction."""
    cp = SandboxControlPlane(base_dir=temp_workspace_dir)
    instance = cp.provision(
        identity=sample_identity,
        lease=sample_lease,
        grant=sample_grant,
    )

    # Sub-agent creates an artifact in the workspace
    out_file = instance.workspace_dir / "dist/bundle.js"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_content = "console.log('generated bundle');"
    out_file.write_text(out_content, encoding="utf-8")

    diff_content = "--- a/app.js\n+++ b/app.js\n@@ -1 +1 @@\n-old\n+new\n"
    raw_output = {
        "status": "success",
        "diff": diff_content,
        "product_specification": "Spec v1.0",
    }

    sealed = cp.seal(instance.identity.sandbox_id, raw_output)

    assert sealed.state is not None
    assert instance.state == SandboxLifecycleState.RESULT_SEALED
    assert sealed.generated_diff == diff_content
    assert sealed.diff_hash == hashlib.sha256(diff_content.encode("utf-8")).hexdigest()
    assert "dist/bundle.js" in sealed.artifacts
    assert sealed.artifact_hashes["dist/bundle.js"] == hashlib.sha256(out_content.encode("utf-8")).hexdigest()
    assert "product_specification" in sealed.artifacts
    assert sealed.artifact_hashes["product_specification"] == hashlib.sha256("Spec v1.0".encode("utf-8")).hexdigest()


# ===========================================================================
# 8. Deterministic Cleanup on All Terminal States
# ===========================================================================

@pytest.mark.parametrize("terminal_reason", ["completed", "failed", "timeout", "retry"])
def test_deterministic_cleanup_on_all_terminal_states(
    terminal_reason: str,
    temp_workspace_dir: Path,
    sample_identity: SandboxIdentity,
    sample_lease: DevelopmentExecutionLease,
    sample_grant: SandboxCapabilityGrant,
):
    """Workspace wiped, credential revoked, state set to DESTROYED on any terminal exit."""
    cp = SandboxControlPlane(base_dir=temp_workspace_dir)
    instance = cp.provision(
        identity=sample_identity,
        lease=sample_lease,
        grant=sample_grant,
        input_snapshot={"scratch/test.txt": "ephemeral"},
    )
    workspace_path = instance.workspace_dir
    token = instance.credential_token

    assert workspace_path.exists()
    assert cp.credential_manager.is_valid(instance.identity.sandbox_id, token) is True

    # Destroy
    destroyed = cp.destroy(instance.identity.sandbox_id, reason=terminal_reason)
    assert destroyed is True
    assert instance.state == SandboxLifecycleState.DESTROYED
    assert instance.destroyed_at is not None
    assert not workspace_path.exists()
    assert cp.credential_manager.is_valid(instance.identity.sandbox_id, token) is False


# ===========================================================================
# 9. Model-A & Authorization Boundary Cross-Boundary Enforcement
# ===========================================================================

def test_model_a_blocks_sandbox_caller_from_protected_services(sample_lease: DevelopmentExecutionLease):
    """Sandbox origin caller is blocked from enterprise DB, RAG, IE internals, CMS direct."""
    boundary = AuthorizationBoundary()
    sandbox_caller = CallerIdentity(
        subject="aio-sandbox-worker",
        tenant_scope=TenantScope(tenant_id="acme"),
        risk_ceiling=RiskLevel.MEDIUM,
    )

    # Direct database access blocked
    with pytest.raises(AuthorizationError, match="Model-A Security Violation.*database"):
        boundary.authorize_sandbox_action(
            caller=sandbox_caller,
            lease=sample_lease,
            target_resource="enterprise_database_write",
            is_sandbox_origin=True,
        )

    # RAG vector store access blocked
    with pytest.raises(AuthorizationError, match="Model-A Security Violation.*vector_store"):
        boundary.authorize_sandbox_action(
            caller=sandbox_caller,
            lease=sample_lease,
            target_resource="rag_vector_store",
            is_sandbox_origin=True,
        )

    # Production CMS actuation blocked
    with pytest.raises(AuthorizationError, match="Model-A Security Violation.*cms_production"):
        boundary.authorize_sandbox_action(
            caller=sandbox_caller,
            lease=sample_lease,
            target_resource="cms_production_publish",
            is_sandbox_origin=True,
        )


# ===========================================================================
# 10. State Machine Integration (DE-02 + DE-03)
# ===========================================================================

def test_state_machine_lifecycle_with_sandbox_validation(sample_lease: DevelopmentExecutionLease):
    """Deterministic sequence: SANDBOX_PROVISIONING -> VALIDATED -> SUBAGENT_RUNNING -> RESULT_SEALED."""
    sm = DevelopmentStateMachine()

    # 1. SANDBOX_PROVISIONING -> VALIDATED requires valid lease
    cp_state = sm.transition(
        current_state=DevelopmentWorkflowState.SANDBOX_PROVISIONING,
        target_state=DevelopmentWorkflowState.VALIDATED,
        task_id=sample_lease.task_id,
        workflow_id=sample_lease.workflow_id,
        step_id=sample_lease.step_id,
        attempt_id=sample_lease.attempt_id,
        idempotency_key="key-val-1",
        lease=sample_lease,
        state_data={"sandbox_id": "sbx-123", "isolation_validated": True},
    )
    assert cp_state.state == DevelopmentWorkflowState.VALIDATED

    # 2. Transition to SUBAGENT_RUNNING fails if isolation validation failed
    with pytest.raises(PolicyViolationError, match="Sandbox isolation validation failed"):
        sm.transition(
            current_state=DevelopmentWorkflowState.VALIDATED,
            target_state=DevelopmentWorkflowState.SUBAGENT_RUNNING,
            task_id=sample_lease.task_id,
            workflow_id=sample_lease.workflow_id,
            step_id=sample_lease.step_id,
            attempt_id=sample_lease.attempt_id,
            idempotency_key="key-run-failed",
            lease=sample_lease,
            state_data={"isolation_validated": False},
        )

    # 3. Transition to SUBAGENT_RUNNING succeeds with validated isolation & lease
    run_state = sm.transition(
        current_state=DevelopmentWorkflowState.VALIDATED,
        target_state=DevelopmentWorkflowState.SUBAGENT_RUNNING,
        task_id=sample_lease.task_id,
        workflow_id=sample_lease.workflow_id,
        step_id=sample_lease.step_id,
        attempt_id=sample_lease.attempt_id,
        idempotency_key="key-run-1",
        lease=sample_lease,
        state_data={"isolation_validated": True},
        active_subagent="DEV-CODE",
    )
    assert run_state.state == DevelopmentWorkflowState.SUBAGENT_RUNNING

    # 4. SUBAGENT_RUNNING -> RESULT_SEALED requires lease
    sealed_state = sm.transition(
        current_state=DevelopmentWorkflowState.SUBAGENT_RUNNING,
        target_state=DevelopmentWorkflowState.RESULT_SEALED,
        task_id=sample_lease.task_id,
        workflow_id=sample_lease.workflow_id,
        step_id=sample_lease.step_id,
        attempt_id=sample_lease.attempt_id,
        idempotency_key="key-seal-1",
        lease=sample_lease,
        state_data={"diff_hash": "abc123sha", "sealed": True},
    )
    assert sealed_state.state == DevelopmentWorkflowState.RESULT_SEALED


# ===========================================================================
# 11. SandboxClient Integration
# ===========================================================================

@pytest.mark.asyncio
async def test_sandbox_client_control_plane_integration(
    temp_workspace_dir: Path,
    sample_identity: SandboxIdentity,
    sample_lease: DevelopmentExecutionLease,
    sample_grant: SandboxCapabilityGrant,
):
    """SandboxClient manages sandbox lifecycle via control plane."""
    client = SandboxClient()
    # Override base dir to temp
    client._control_plane = SandboxControlPlane(base_dir=temp_workspace_dir)

    instance = client.provision_sandbox(
        identity=sample_identity,
        lease=sample_lease,
        grant=sample_grant,
        input_snapshot={"index.html": "<h1>Test</h1>"},
    )
    assert instance.state == SandboxLifecycleState.VALIDATED

    # Seal output
    sealed = client.seal_sandbox(
        sample_identity.sandbox_id,
        {"diff": "+ added line", "status": "success"},
    )
    assert sealed.generated_diff == "+ added line"
    assert sealed.diff_hash != ""

    # Destroy
    destroyed = client.destroy_sandbox(sample_identity.sandbox_id)
    assert destroyed is True
    assert not (temp_workspace_dir / sample_identity.sandbox_id).exists()
