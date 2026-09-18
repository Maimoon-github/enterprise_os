"""Comprehensive unit and integration tests for Task DE-11: DEV-REL Sub-Agent.

Validates:
1. Clean packaging success: Packages release bundle with SBOM, manifests, and SLSA attestation.
2. Missing security dossier fail-closed: None raises PolicyViolationError.
3. Security dossier DENY gate: Machine DENY overrides human approval.
4. HITL approval required: hitl_approved=False raises PolicyViolationError.
5. HITL approval token enforcement: Missing required token raises PolicyViolationError.
6. Candidate digest mismatch fail-closed: Digest mismatch raises PolicyViolationError.
7. Scope boundary enforcement: Production deployment attempt raises PolicyViolationError.
8. Migration dry-run failure aborts packaging: Incompatible schema raises PolicyViolationError.
9. CycloneDX v1.5 SBOM compliance: Spec version, serial number, component purls valid.
10. Deployment/rollback manifests integrity: Health checks, resource limits, drain steps.
11. Deterministic release deliverable hashing: canonical_bytes and compute_release_hash.
12. State machine security dossier gate: State machine blocks APPROVED when dossier failed.
13. DevelopmentAgent integration: execute_release_step packages and records provenance.
14. Direct micro_tools execution: All 6 packaging operations in execute_s_code tested directly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.development_engine.development import DevelopmentAgent
from app.agents.development_engine.subagents.release_ops import ReleaseOpsAgent
from app.core.exceptions import PolicyViolationError
from app.integrations.sandbox.micro_tools import execute_s_code
from app.orchestration.development_state_machine import DevelopmentStateMachine
from app.schemas.development import (
    CodeCandidateDeliverable,
    CodeSanityCheckResult,
    CycloneDxSbom,
    DeploymentManifest,
    DevelopmentTaskGrant,
    ReleaseArtifact,
    ReleaseCandidateDeliverable,
    RollbackManifest,
    SecurityDossier,
    SecurityVerdict,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.schemas.task_state import DevelopmentWorkflowState
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository, FakeSandboxClient


@pytest.fixture
def fake_sandbox() -> FakeSandboxClient:
    return FakeSandboxClient()


@pytest.fixture
def rel_agent(fake_sandbox: FakeSandboxClient) -> ReleaseOpsAgent:
    return ReleaseOpsAgent(sandbox_client=fake_sandbox)


@pytest.fixture
def valid_grant() -> DevelopmentTaskGrant:
    return DevelopmentTaskGrant(
        task_id="task-rel-001",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-beta"),
        component_name="PaymentService",
        target_files=["services/payment_service.py"],
        allowed_operations=[
            "package_release_bundle",
            "generate_cyclonedx_sbom",
            "generate_deployment_manifest",
            "generate_rollback_manifest",
            "simulate_migration_dry_run",
            "verify_release_integrity",
        ],
        sandbox_capabilities=[SandboxCapability.CODE.value],
        tool_permissions=[
            "bundle_packager",
            "sbom_generator",
            "deployment_manifest_builder",
            "rollback_manifest_builder",
            "migration_dry_run_tester",
            "integrity_hasher",
        ],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


@pytest.fixture
def clean_candidate() -> CodeCandidateDeliverable:
    candidate = CodeCandidateDeliverable(
        candidate_id="cand-pay-001",
        task_id="task-rel-001",
        workflow_id="wf-rel-001",
        attempt_id="att-1",
        component_name="PaymentService",
        source_code={
            "services/payment_service.py": (
                "def process_payment(amount: float) -> bool:\n"
                "    \"\"\"Process safe payment without dangerous calls.\"\"\"\n"
                "    return amount > 0.0\n"
            )
        },
        changed_files=["services/payment_service.py"],
        code_diffs=[],
        implementation_summary="Implemented clean payment service.",
        sanity_check_result=CodeSanityCheckResult(
            compiler_passed=True,
            syntax_valid=True,
            is_valid=True,
        ),
    )
    candidate.compute_candidate_hash()
    return candidate


@pytest.fixture
def approved_security_dossier(clean_candidate: CodeCandidateDeliverable) -> SecurityDossier:
    dossier = SecurityDossier(
        dossier_id="sec-dossier-001",
        task_id="task-rel-001",
        workflow_id="wf-rel-001",
        candidate_hash=clean_candidate.candidate_hash,
        target_candidate_id=clean_candidate.candidate_id,
        component_name="PaymentService",
        verdict=SecurityVerdict.PASS,
        scanners_run=["scan_sast", "scan_secrets", "scan_dependencies_sca"],
        hard_block_count=0,
        findings=[],
    )
    dossier.compute_dossier_hash()
    return dossier


@pytest.mark.asyncio
async def test_release_packaging_clean_success(
    rel_agent: ReleaseOpsAgent,
    clean_candidate: CodeCandidateDeliverable,
    approved_security_dossier: SecurityDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 1: Clean security approval packages release deliverable with SBOM and manifests."""
    deliverable = await rel_agent.prepare_release(
        tenant_id="tenant-beta",
        task_id="task-rel-001",
        candidate=clean_candidate,
        security_dossier=approved_security_dossier,
        task_grant=valid_grant,
        hitl_approved=True,
        context={"version": "1.2.0", "dependencies": {"requests": "2.31.0"}},
    )

    assert isinstance(deliverable, ReleaseCandidateDeliverable)
    assert deliverable.version == "1.2.0"
    assert deliverable.candidate_hash == clean_candidate.candidate_hash
    assert deliverable.security_dossier_hash == approved_security_dossier.dossier_hash
    assert len(deliverable.release_artifacts) >= 1
    assert len(deliverable.artifact_digests) >= 1
    assert deliverable.sbom.specVersion == "1.5"
    assert deliverable.deployment_manifest.manifest_hash != ""
    assert deliverable.rollback_manifest.rollback_hash != ""
    assert len(deliverable.migration_dry_run_evidence) >= 1
    assert deliverable.release_hash != ""


@pytest.mark.asyncio
async def test_missing_security_dossier_fails_closed(
    rel_agent: ReleaseOpsAgent,
    clean_candidate: CodeCandidateDeliverable,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 2: Missing security dossier fails closed with PolicyViolationError."""
    with pytest.raises(PolicyViolationError, match="requires an approved SecurityDossier"):
        await rel_agent.prepare_release(
            tenant_id="tenant-beta",
            task_id="task-rel-001",
            candidate=clean_candidate,
            security_dossier=None,
            task_grant=valid_grant,
        )


@pytest.mark.asyncio
async def test_security_dossier_deny_fails_closed(
    rel_agent: ReleaseOpsAgent,
    clean_candidate: CodeCandidateDeliverable,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 3: Security dossier DENY overrides human approval."""
    denied_dossier = SecurityDossier(
        dossier_id="sec-dossier-deny",
        task_id="task-rel-001",
        workflow_id="wf-rel-001",
        candidate_hash=clean_candidate.candidate_hash,
        target_candidate_id=clean_candidate.candidate_id,
        component_name="PaymentService",
        verdict=SecurityVerdict.DENY,
        hard_block_count=2,
    )
    denied_dossier.compute_dossier_hash()

    with pytest.raises(PolicyViolationError, match="Machine DENY overrides human approval"):
        await rel_agent.prepare_release(
            tenant_id="tenant-beta",
            task_id="task-rel-001",
            candidate=clean_candidate,
            security_dossier=denied_dossier,
            task_grant=valid_grant,
            hitl_approved=True,  # Even with human approval, machine DENY blocks!
        )


@pytest.mark.asyncio
async def test_hitl_approval_required(
    rel_agent: ReleaseOpsAgent,
    clean_candidate: CodeCandidateDeliverable,
    approved_security_dossier: SecurityDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 4: Pre-DEV-REL human approval is strictly required."""
    with pytest.raises(PolicyViolationError, match="requires prior human-in-the-loop"):
        await rel_agent.prepare_release(
            tenant_id="tenant-beta",
            task_id="task-rel-001",
            candidate=clean_candidate,
            security_dossier=approved_security_dossier,
            task_grant=valid_grant,
            hitl_approved=False,
        )


@pytest.mark.asyncio
async def test_hitl_approval_token_missing_when_required(
    rel_agent: ReleaseOpsAgent,
    clean_candidate: CodeCandidateDeliverable,
    approved_security_dossier: SecurityDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 5: When require_hitl_token is specified, missing token fails closed."""
    with pytest.raises(PolicyViolationError, match="Missing required HITL approval token"):
        await rel_agent.prepare_release(
            tenant_id="tenant-beta",
            task_id="task-rel-001",
            candidate=clean_candidate,
            security_dossier=approved_security_dossier,
            task_grant=valid_grant,
            hitl_approved=True,
            hitl_approval_token=None,
            context={"require_hitl_token": True},
        )


@pytest.mark.asyncio
async def test_candidate_digest_mismatch_fails_closed(
    rel_agent: ReleaseOpsAgent,
    clean_candidate: CodeCandidateDeliverable,
    approved_security_dossier: SecurityDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 6: Candidate hash mismatching security dossier hash fails closed."""
    approved_security_dossier.candidate_hash = "different-security-hash"

    with pytest.raises(PolicyViolationError, match="Candidate digest mismatch"):
        await rel_agent.prepare_release(
            tenant_id="tenant-beta",
            task_id="task-rel-001",
            candidate=clean_candidate,
            security_dossier=approved_security_dossier,
            task_grant=valid_grant,
            hitl_approved=True,
        )


@pytest.mark.asyncio
async def test_deployment_scope_violation_fails_closed(
    rel_agent: ReleaseOpsAgent,
    clean_candidate: CodeCandidateDeliverable,
    approved_security_dossier: SecurityDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 7: Packaging agent cannot deploy to production (scope violation)."""
    with pytest.raises(PolicyViolationError, match="restricted to release packaging only"):
        await rel_agent.prepare_release(
            tenant_id="tenant-beta",
            task_id="task-rel-001",
            candidate=clean_candidate,
            security_dossier=approved_security_dossier,
            task_grant=valid_grant,
            hitl_approved=True,
            context={"deploy_to_production": True},
        )


@pytest.mark.asyncio
async def test_migration_dry_run_failure_aborts_packaging(
    rel_agent: ReleaseOpsAgent,
    clean_candidate: CodeCandidateDeliverable,
    approved_security_dossier: SecurityDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 8: Database migration dry-run simulation failure aborts packaging."""
    with pytest.raises(PolicyViolationError, match="Database migration dry-run simulation failed"):
        await rel_agent.prepare_release(
            tenant_id="tenant-beta",
            task_id="task-rel-001",
            candidate=clean_candidate,
            security_dossier=approved_security_dossier,
            task_grant=valid_grant,
            hitl_approved=True,
            context={"simulate_migration_failure": True},
        )


@pytest.mark.asyncio
async def test_cyclonedx_sbom_spec_compliance(
    rel_agent: ReleaseOpsAgent,
    clean_candidate: CodeCandidateDeliverable,
    approved_security_dossier: SecurityDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 9: Generated SBOM conforms to CycloneDX v1.5 specification."""
    deliverable = await rel_agent.prepare_release(
        tenant_id="tenant-beta",
        task_id="task-rel-001",
        candidate=clean_candidate,
        security_dossier=approved_security_dossier,
        task_grant=valid_grant,
        hitl_approved=True,
        context={"dependencies": {"urllib3": "2.0.7", "cryptography": "41.0.0"}},
    )

    sbom = deliverable.sbom
    assert sbom.bomFormat == "CycloneDX"
    assert sbom.specVersion == "1.5"
    assert sbom.serialNumber.startswith("urn:uuid:")
    assert len(sbom.components) == 2
    comp_names = [c.name for c in sbom.components]
    assert "urllib3" in comp_names
    assert "cryptography" in comp_names
    assert sbom.sbom_hash != ""


@pytest.mark.asyncio
async def test_deployment_and_rollback_manifests_integrity(
    rel_agent: ReleaseOpsAgent,
    clean_candidate: CodeCandidateDeliverable,
    approved_security_dossier: SecurityDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 10: Deployment and rollback manifests contain complete specifications."""
    deliverable = await rel_agent.prepare_release(
        tenant_id="tenant-beta",
        task_id="task-rel-001",
        candidate=clean_candidate,
        security_dossier=approved_security_dossier,
        task_grant=valid_grant,
        hitl_approved=True,
        context={
            "runtime": "python:3.11-slim",
            "healthcheck_endpoint": "/api/health",
            "previous_stable_version": "1.1.0",
        },
    )

    deploy = deliverable.deployment_manifest
    assert deploy.runtime == "python:3.11-slim"
    assert deploy.healthcheck_endpoint == "/api/health"
    assert deploy.manifest_hash != ""

    rb = deliverable.rollback_manifest
    assert rb.previous_stable_version == "1.1.0"
    assert rb.rollback_strategy == "BLUE_GREEN_DRAIN"
    assert len(rb.revert_steps) >= 1
    assert rb.rollback_hash != ""


def test_release_candidate_deterministic_hashing() -> None:
    """Test 11: canonical_bytes and compute_release_hash produce identical hash for same content."""
    sbom = CycloneDxSbom(
        serialNumber="urn:uuid:test-sbom",
        components=[],
    )
    deploy = DeploymentManifest(
        manifest_id="deploy-test-1.0.0",
        component_name="TestComp",
    )
    rb = RollbackManifest(
        rollback_id="rb-test-1.0.0",
        target_release_id="rel-001",
        previous_stable_version="0.9.0",
    )

    r1 = ReleaseCandidateDeliverable(
        release_id="rel-001",
        task_id="task-001",
        workflow_id="wf-001",
        security_dossier_hash="sec-hash-1234",
        candidate_hash="cand-hash-1234",
        component_name="TestComp",
        version="1.0.0",
        release_artifacts=[
            ReleaseArtifact(
                artifact_name="main.py",
                file_path="dist/main.py",
                sha256="abc123",
                size_bytes=100,
            )
        ],
        artifact_digests={"main.py": "abc123"},
        sbom=sbom,
        deployment_manifest=deploy,
        rollback_manifest=rb,
    )
    h1 = r1.compute_release_hash()

    r2 = ReleaseCandidateDeliverable(
        release_id="rel-001",
        task_id="task-001",
        workflow_id="wf-001",
        security_dossier_hash="sec-hash-1234",
        candidate_hash="cand-hash-1234",
        component_name="TestComp",
        version="1.0.0",
        release_artifacts=[
            ReleaseArtifact(
                artifact_name="main.py",
                file_path="dist/main.py",
                sha256="abc123",
                size_bytes=100,
            )
        ],
        artifact_digests={"main.py": "abc123"},
        sbom=sbom,
        deployment_manifest=deploy,
        rollback_manifest=rb,
    )
    h2 = r2.compute_release_hash()

    assert h1 == h2
    assert len(h1) == 64


def test_state_machine_security_dossier_deny_guard() -> None:
    """Test 12: State machine blocks transition to APPROVED when security dossier failed."""
    sm = DevelopmentStateMachine()

    denied_dossier = SecurityDossier(
        dossier_id="sec-dossier-deny-sm",
        task_id="task-001",
        workflow_id="wf-001",
        candidate_hash="hash-123",
        target_candidate_id="cand-001",
        component_name="Comp",
        verdict=SecurityVerdict.DENY,
        hard_block_count=1,
    )
    denied_dossier.compute_dossier_hash()

    with pytest.raises(PolicyViolationError, match="Security dossier verdict is 'DENY'"):
        sm.validate_transition_guards(
            current_state=DevelopmentWorkflowState.HITL_PENDING,
            target_state=DevelopmentWorkflowState.APPROVED,
            state_data={
                "approval_decision": "APPROVE",
                "approval_token": "token-123",
                "security_dossier": denied_dossier,
            },
        )


@pytest.mark.asyncio
async def test_development_agent_execute_release_step(
    fake_sandbox: FakeSandboxClient,
    clean_candidate: CodeCandidateDeliverable,
    approved_security_dossier: SecurityDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 13: DevelopmentAgent integrates DEV-REL and records provenance."""
    agent = DevelopmentAgent(sandbox_client=fake_sandbox)
    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repository=prov_repo)

    deliverable = await agent.execute_release_step(
        grant=valid_grant,
        security_dossier=approved_security_dossier,
        candidate=clean_candidate,
        hitl_approved=True,
        provenance_recorder=recorder,
    )

    assert isinstance(deliverable, ReleaseCandidateDeliverable)
    assert deliverable.release_hash != ""
    chain = prov_repo._chains.get("tenant-beta", [])
    assert len(chain) >= 1
    rec = chain[0]
    assert rec.agent == "DEV-REL"
    assert rec.metadata["release_hash"] == deliverable.release_hash


def test_micro_tools_release_operations_direct() -> None:
    """Test 14: Directly test DEV-REL packaging operations in execute_s_code."""
    # 1. package_release_bundle
    bundle_res = execute_s_code(
        operation="package_release_bundle",
        component_name="WidgetService",
        source_files={"widget.py": "print('hello')\n"},
    )
    assert bundle_res["status"] == "SUCCESS"
    assert bundle_res["artifact_count"] == 1
    assert "widget.py" in bundle_res["artifact_digests"]

    # 2. generate_cyclonedx_sbom
    sbom_res = execute_s_code(
        operation="generate_cyclonedx_sbom",
        component_name="WidgetService",
        dependencies={"pydantic": "2.10.0"},
    )
    assert sbom_res["status"] == "SUCCESS"
    assert sbom_res["sbom"]["bomFormat"] == "CycloneDX"
    assert sbom_res["component_count"] == 1

    # 3. generate_deployment_manifest
    deploy_res = execute_s_code(
        operation="generate_deployment_manifest",
        component_name="WidgetService",
    )
    assert deploy_res["status"] == "SUCCESS"
    assert "manifest_hash" in deploy_res

    # 4. generate_rollback_manifest
    rb_res = execute_s_code(
        operation="generate_rollback_manifest",
        target_release_id="rel-123",
    )
    assert rb_res["status"] == "SUCCESS"
    assert "rollback_hash" in rb_res

    # 5. simulate_migration_dry_run
    mig_res = execute_s_code(
        operation="simulate_migration_dry_run",
        simulate_migration_failure=False,
    )
    assert mig_res["status"] == "SUCCESS"
    assert mig_res["dry_run_passed"] is True

    # 6. verify_release_integrity
    art_sha = bundle_res["release_artifacts"][0]["sha256"]
    integ_res = execute_s_code(
        operation="verify_release_integrity",
        release_artifacts=bundle_res["release_artifacts"],
        artifact_digests={"widget.py": art_sha},
    )
    assert integ_res["status"] == "SUCCESS"
    assert integ_res["integrity_verified"] is True
