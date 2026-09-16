"""Focused unit and integration tests for Task DE-06: DEV-PLAN.

Validates:
1. DEV-PLAN accepts only bounded, valid task grants (fails closed on invalid/expired grants).
2. Read-only repository inspection in sandbox with mutation denial.
3. Structured DevelopmentPlan output conforming to all required fields.
4. Correct sub-agent ordering (DEV-CMS -> DEV-UI -> DEV-CODE -> DEV-VERIFY -> DEV-SEC -> DEV-REL).
5. Conditional exclusion of DEV-CMS/DEV-UI/DEV-CODE with non-empty skip_reason.
6. Fail-closed policy validation preventing skipping DEV-VERIFY, DEV-SEC, or DEV-REL on release-producing plans.
7. Rejection & revision attempt handling (att-1 -> att-2) preserving immutability of previous plans.
8. Deterministic canonical bytes and SHA-256 plan hash computation.
9. Integration with DevelopmentAgent and ProvenanceRecorder.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from typing import Any
import pytest

from app.agents.development_engine.development import DevelopmentAgent
from app.agents.development_engine.subagents.planning import DevelopmentPlanningAgent
from app.core.exceptions import PolicyViolationError
from app.integrations.sandbox.micro_tools import execute_s_code
from app.schemas.agent_contracts import TaskGrant
from app.schemas.development import (
    DevelopmentPlan,
    DevelopmentPlanStep,
    DevelopmentTaskGrant,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository, FakeSandboxClient


@pytest.fixture
def fake_sandbox() -> FakeSandboxClient:
    return FakeSandboxClient()


@pytest.fixture
def planning_agent(fake_sandbox: FakeSandboxClient) -> DevelopmentPlanningAgent:
    return DevelopmentPlanningAgent(fake_sandbox)


@pytest.fixture
def dev_agent(fake_sandbox: FakeSandboxClient) -> DevelopmentAgent:
    return DevelopmentAgent(fake_sandbox)


@pytest.fixture
def valid_grant() -> DevelopmentTaskGrant:
    return DevelopmentTaskGrant(
        task_id="task-plan-001",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-acme"),
        brand_id="brand-core",
        objective="Add responsive navigation bar with CMS schema updates",
        component_name="NavbarComponent",
        target_files=[
            "schemas/navigation.json",
            "templates/navbar.html",
            "components/navbar.py",
        ],
        token_budget=8000,
        expires_at=datetime.now(UTC) + timedelta(minutes=45),
        sandbox_capabilities=[SandboxCapability.CODE.value],
    )


@pytest.fixture
def backend_only_grant() -> DevelopmentTaskGrant:
    return DevelopmentTaskGrant(
        task_id="task-plan-002",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-acme"),
        brand_id="brand-core",
        objective="Optimize database query performance in auth service",
        component_name="AuthService",
        target_files=["services/auth.py", "core/db.py"],
        token_budget=6000,
        expires_at=datetime.now(UTC) + timedelta(minutes=45),
        sandbox_capabilities=[SandboxCapability.CODE.value],
    )


# ===========================================================================
# 1. Full Pipeline Plan Generation Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_full_pipeline_plan_generation(
    planning_agent: DevelopmentPlanningAgent, valid_grant: DevelopmentTaskGrant
) -> None:
    """DEV-PLAN generates a complete 6-step plan when all sub-agents are required."""
    plan = await planning_agent.create_plan(
        grant=valid_grant,
        workflow_id="wf-test-100",
        attempt_id="att-1",
        is_release_producing=True,
    )

    assert plan.plan_id.startswith("plan-")
    assert plan.task_id == valid_grant.task_id
    assert plan.workflow_id == "wf-test-100"
    assert plan.attempt_id == "att-1"
    assert plan.plan_version in (1, "1", "1.0.0")
    assert plan.status in ("DRAFT", "SEALED")
    assert len(plan.steps) == 6

    # Verify correct subagent names and ordering
    expected_subagents = [
        "DEV-CMS",
        "DEV-UI",
        "DEV-CODE",
        "DEV-VERIFY",
        "DEV-SEC",
        "DEV-REL",
    ]
    actual_subagents = [s.subagent for s in plan.steps]
    assert actual_subagents == expected_subagents

    # All should be REQUIRED for full stack task
    for step in plan.steps:
        assert step.status == "REQUIRED"
        assert step.skip_reason is None

    # Step dependencies should follow topological ordering
    step_map = {s.subagent: s for s in plan.steps}
    assert step_map["DEV-CMS"].dependencies == []
    assert "step-01-cms" in step_map["DEV-UI"].dependencies
    assert "step-02-ui" in step_map["DEV-CODE"].dependencies
    assert "step-03-code" in step_map["DEV-VERIFY"].dependencies
    assert "step-04-verify" in step_map["DEV-SEC"].dependencies
    assert "step-05-sec" in step_map["DEV-REL"].dependencies

    # Plan hash must be computed and valid
    assert plan.plan_hash is not None
    assert len(plan.plan_hash) == 64
    assert plan.plan_hash == plan.compute_plan_hash()


# ===========================================================================
# 2. Conditional Exclusion Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_conditional_exclusion_backend_only_task(
    planning_agent: DevelopmentPlanningAgent, backend_only_grant: DevelopmentTaskGrant
) -> None:
    """DEV-PLAN conditionally marks DEV-CMS and DEV-UI as SKIPPED_NOT_APPLICABLE with skip_reason."""
    plan = await planning_agent.create_plan(
        grant=backend_only_grant,
        workflow_id="wf-test-200",
        attempt_id="att-1",
        is_release_producing=True,
    )

    step_map = {s.subagent: s for s in plan.steps}

    # DEV-CMS and DEV-UI should be skipped
    assert step_map["DEV-CMS"].status == "SKIPPED_NOT_APPLICABLE"
    assert step_map["DEV-CMS"].skip_reason is not None
    assert len(step_map["DEV-CMS"].skip_reason.strip()) > 0

    assert step_map["DEV-UI"].status == "SKIPPED_NOT_APPLICABLE"
    assert step_map["DEV-UI"].skip_reason is not None
    assert len(step_map["DEV-UI"].skip_reason.strip()) > 0

    # DEV-CODE, DEV-VERIFY, DEV-SEC, DEV-REL MUST remain REQUIRED
    assert step_map["DEV-CODE"].status == "REQUIRED"
    assert step_map["DEV-VERIFY"].status == "REQUIRED"
    assert step_map["DEV-SEC"].status == "REQUIRED"
    assert step_map["DEV-REL"].status == "REQUIRED"

    # Validate policy passes
    plan.validate_policy(is_release_producing=True)


# ===========================================================================
# 3. Policy Enforcement & Fail-Closed Validation Tests
# ===========================================================================

def test_policy_fails_if_mandatory_subagents_skipped() -> None:
    """Fail-closed policy violation if DEV-VERIFY, DEV-SEC, or DEV-REL are skipped in release-producing plan."""
    steps = [
        DevelopmentPlanStep(
            step_id="step-1",
            subagent="DEV-CODE",
            order=1,
            description="Code step",
            status="REQUIRED",
            acceptance_criteria=["Tests pass"],
        ),
        DevelopmentPlanStep(
            step_id="step-2",
            subagent="DEV-VERIFY",
            order=2,
            description="Verify step",
            status="SKIPPED_NOT_APPLICABLE",  # Invalid for release-producing
            skip_reason="Trying to skip verification",
            acceptance_criteria=["Tests pass"],
        ),
        DevelopmentPlanStep(
            step_id="step-3",
            subagent="DEV-SEC",
            order=3,
            description="Sec step",
            status="REQUIRED",
            acceptance_criteria=["Sec passes"],
        ),
        DevelopmentPlanStep(
            step_id="step-4",
            subagent="DEV-REL",
            order=4,
            description="Release step",
            status="REQUIRED",
            acceptance_criteria=["Release artifact ready"],
        ),
    ]

    plan = DevelopmentPlan(
        plan_id="plan-invalid-1",
        task_id="task-invalid-1",
        workflow_id="wf-1",
        attempt_id="att-1",
        plan_version=1,
        objective="Test invalid skipping",
        architecture_summary="Arch",
        change_impact_summary="Impact",
        affected_files=["test.py"],
        steps=steps,
    )

    with pytest.raises(PolicyViolationError) as exc_info:
        plan.validate_policy(is_release_producing=True)
    assert "cannot be excluded" in str(exc_info.value) or "DEV-VERIFY is mandatory" in str(exc_info.value)


def test_policy_fails_if_skipped_without_reason() -> None:
    """Fail-closed policy violation if DEV-CMS is skipped without an explicit skip_reason."""
    with pytest.raises(ValueError) as exc_info:
        DevelopmentPlanStep(
            step_id="step-1",
            subagent="DEV-CMS",
            order=1,
            description="CMS step",
            status="SKIPPED_NOT_APPLICABLE",
            skip_reason=None,  # Invalid: must provide reason
            acceptance_criteria=[],
        )
    assert "skip_reason" in str(exc_info.value)


def test_policy_fails_on_dependency_cycle() -> None:
    """Fail-closed policy violation if circular / forward dependency exists between steps."""
    steps = [
        DevelopmentPlanStep(
            step_id="step-1",
            subagent="DEV-CODE",
            order=1,
            description="Code step",
            status="REQUIRED",
            dependencies=["step-2"],  # Forward dependency prohibited
            acceptance_criteria=["Criterion"],
        ),
        DevelopmentPlanStep(
            step_id="step-2",
            subagent="DEV-VERIFY",
            order=2,
            description="Verify step",
            status="REQUIRED",
            dependencies=["step-1"],
            acceptance_criteria=["Criterion"],
        ),
        DevelopmentPlanStep(
            step_id="step-3",
            subagent="DEV-SEC",
            order=3,
            description="Sec step",
            status="REQUIRED",
            dependencies=["step-2"],
            acceptance_criteria=["Criterion"],
        ),
        DevelopmentPlanStep(
            step_id="step-4",
            subagent="DEV-REL",
            order=4,
            description="Rel step",
            status="REQUIRED",
            dependencies=["step-3"],
            acceptance_criteria=["Criterion"],
        ),
    ]

    plan = DevelopmentPlan(
        plan_id="plan-cycle",
        task_id="task-cycle",
        workflow_id="wf-1",
        attempt_id="att-1",
        plan_version=1,
        objective="Test dependency cycle",
        architecture_summary="Arch",
        change_impact_summary="Impact",
        affected_files=["test.py"],
        steps=steps,
    )

    with pytest.raises(PolicyViolationError) as exc_info:
        plan.validate_policy(is_release_producing=True)
    assert "not an earlier step" in str(exc_info.value)


# ===========================================================================
# 4. Deterministic Hash & Canonical Bytes Tests
# ===========================================================================

def test_canonical_bytes_and_hash_determinism() -> None:
    """Plan hash computation is deterministic and changes upon mutation."""
    step = DevelopmentPlanStep(
        step_id="s1",
        subagent="DEV-CODE",
        order=1,
        description="Write code",
        status="REQUIRED",
        acceptance_criteria=["Tests pass"],
    )
    plan1 = DevelopmentPlan(
        plan_id="plan-det",
        task_id="task-det",
        workflow_id="wf-det",
        attempt_id="att-1",
        plan_version=1,
        objective="Objective",
        architecture_summary="Arch",
        change_impact_summary="Impact",
        affected_files=["a.py"],
        steps=[step],
    )

    hash1 = plan1.compute_plan_hash()
    assert hash1 == plan1.compute_plan_hash()

    # Create identical plan and verify hash matches
    plan2 = DevelopmentPlan(
        plan_id="plan-det",
        task_id="task-det",
        workflow_id="wf-det",
        attempt_id="att-1",
        plan_version=1,
        objective="Objective",
        architecture_summary="Arch",
        change_impact_summary="Impact",
        affected_files=["a.py"],
        steps=[step],
    )
    assert plan1.canonical_bytes() == plan2.canonical_bytes()
    assert hash1 == plan2.compute_plan_hash()

    # Mutation alters hash
    plan3 = plan1.model_copy(deep=True)
    plan3.objective = "Modified objective"
    assert plan3.compute_plan_hash() != hash1


# ===========================================================================
# 5. Rejection & Revision (Attempt-2 Continuity) Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_rejection_and_revision_flow(
    planning_agent: DevelopmentPlanningAgent, valid_grant: DevelopmentTaskGrant
) -> None:
    """DEV-PLAN creates a new attempt plan incorporating reviewer feedback without mutating previous plan."""
    # Attempt 1
    plan_att1 = await planning_agent.create_plan(
        grant=valid_grant,
        workflow_id="wf-rev-001",
        attempt_id="att-1",
        is_release_producing=True,
    )
    hash_att1 = plan_att1.plan_hash
    assert plan_att1.attempt_id == "att-1"
    assert plan_att1.plan_version in (1, "1")
    assert plan_att1.rejection_feedback is None

    # Reviewer rejects with feedback
    feedback = "Ensure security verification checks for CSRF protection and input sanitization."

    # Attempt 2
    plan_att2 = await planning_agent.create_plan(
        grant=valid_grant,
        workflow_id="wf-rev-001",
        attempt_id="att-2",
        previous_plan=plan_att1,
        reviewer_feedback=feedback,
        is_release_producing=True,
    )

    # Validate Attempt 2 plan properties
    assert plan_att2.attempt_id == "att-2"
    assert plan_att2.plan_version in (2, "2")
    assert plan_att2.rejection_feedback == feedback
    assert plan_att2.plan_hash is not None
    assert plan_att2.plan_hash != hash_att1

    # Verify attempt 1 plan remained untouched and immutable
    assert plan_att1.attempt_id == "att-1"
    assert plan_att1.plan_version in (1, "1")
    assert plan_att1.rejection_feedback is None
    assert plan_att1.plan_hash == hash_att1

    # Acceptance criteria in DEV-SEC should reflect feedback
    sec_step = next(s for s in plan_att2.steps if s.subagent == "DEV-SEC")
    assert any("CSRF" in c or "sanitization" in c for c in sec_step.acceptance_criteria)


# ===========================================================================
# 6. Read-Only Sandbox Enforcement Tests
# ===========================================================================

def test_sandbox_microtool_read_only_enforcement() -> None:
    """Micro-tool execute_s_code denies mutation operations when in read_only mode."""
    # Read-only operation succeeds
    inspect_result = execute_s_code(
        payload={"read_only": True, "files_to_inspect": ["app/main.py"]},
        operation="inspect_files",
    )
    assert inspect_result.get("read_only") is True
    assert "inspected_files" in inspect_result

    # Mutation attempt inside read_only mode fails closed
    write_result = execute_s_code(
        payload={"read_only": True, "path": "app/evil.py", "content": "malicious()"},
        operation="write_file",
    )
    assert write_result.get("security_violation") is True
    assert "denied in read-only" in write_result.get("error", "")

    # apply_diff mutation attempt fails closed
    diff_result = execute_s_code(
        payload={"read_only": True, "diff": "--- +++"},
        operation="apply_diff",
    )
    assert diff_result.get("security_violation") is True
    assert "denied in read-only" in diff_result.get("error", "")


# ===========================================================================
# 7. DevelopmentAgent & Provenance Integration Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_development_agent_planning_with_provenance(
    dev_agent: DevelopmentAgent, valid_grant: DevelopmentTaskGrant
) -> None:
    """DevelopmentAgent orchestrates DEV-PLAN and records complete W3C PROV provenance."""
    fake_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(fake_repo)

    plan, plan_hash = await dev_agent.plan_development_task(
        grant=valid_grant,
        workflow_id="wf-agent-prov-001",
        attempt_id="att-1",
        provenance_recorder=recorder,
    )

    assert plan is not None
    assert plan_hash == plan.plan_hash

    # Check recorded provenance entities and activities in fake_repo._chains
    tenant_id = valid_grant.tenant_scope.tenant_id
    records = fake_repo._chains.get(tenant_id, [])
    assert len(records) >= 1
    rec = records[0]
    assert rec.agent == "DEV-PLAN"
    assert rec.activity.startswith("act-plan-")
    assert rec.metadata.get("plan_hash") == plan_hash
    assert rec.metadata.get("attempt_id") == "att-1"


# ===========================================================================
# 8. Invalid Grant Fail-Closed Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_plan_development_task_rejects_expired_grant(
    dev_agent: DevelopmentAgent, valid_grant: DevelopmentTaskGrant
) -> None:
    """Expired grant is rejected before planning begins."""
    expired_grant = valid_grant.model_copy(
        update={"expires_at": datetime.now(UTC) - timedelta(minutes=5)}
    )

    with pytest.raises(PolicyViolationError) as exc_info:
        await dev_agent.plan_development_task(grant=expired_grant)
    assert "expired" in str(exc_info.value)


@pytest.mark.asyncio
async def test_plan_development_task_rejects_unauthorized_role(
    dev_agent: DevelopmentAgent
) -> None:
    """Non-DEVELOPMENT worker role is rejected."""
    wrong_role_grant = TaskGrant(
        task_id="task-wrong-role",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="tenant-acme"),
        objective="Try unauthorized planning",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    with pytest.raises(PolicyViolationError) as exc_info:
        await dev_agent.plan_development_task(grant=wrong_role_grant)
    assert "Unauthorized worker role" in str(exc_info.value)
