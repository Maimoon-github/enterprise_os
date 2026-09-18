"""Comprehensive unit and integration tests for Task DE-09: DEV-CODE.

Validates:
1. DEV-CODE accepts only approved inputs and hashes.
2. Plan authority enforcement: fails closed if DEV-CODE is skipped or missing.
3. Predecessor verification: validates predecessor candidate hash (DEV-UI / DEV-CMS / DEV-PLAN) and rejects stale predecessor.
4. Scope boundary enforcement: fails closed if proposed mutations target unauthorized files.
5. Tenant isolation breach rejection.
6. Dependency control: fails closed on unauthorized dependency addition/removal; succeeds when authorized.
7. Compiler sanity and AST symbol inspection: repository-native execution checks beyond simple AST parsing.
8. LLM reasoning integration with mock and deterministic offline fallback.
9. Rejection and revision continuity (att-1 -> att-2) preserving att-1 immutability.
10. Deterministic candidate hash sealing and canonical byte stability.
11. Integration with DevelopmentAgent.execute_code_step and ProvenanceRecorder.
12. Direct sandbox micro_tools execution for all DEV-CODE operations (patch, format, inspect AST, compiler sanity, manage packages).
13. HITL handoff deliverable conversion.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from typing import Any
import pytest

from app.agents.development_engine.development import DevelopmentAgent
from app.agents.development_engine.subagents.implementation import CodeImplementationAgent
from app.core.exceptions import PolicyViolationError
from app.integrations.sandbox.micro_tools import execute_s_code
from app.schemas.agent_contracts import CodeDiffEntry, TaskGrant
from app.schemas.cms import CmsCandidateDeliverable, CmsContentModelSchema
from app.schemas.development import (
    CodeCandidateDeliverable,
    CodeSanityCheckResult,
    DependencyChange,
    DependencyChangeAction,
    DevelopmentPlan,
    DevelopmentPlanStep,
    DevelopmentTaskGrant,
    InterfaceChange,
    ToolExecutionEvidence,
    UiAccessibilityReport,
    UiCandidateDeliverable,
    UiRenderEvidence,
    UiValidationEvidence,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository, FakeSandboxClient


class FakeLlmClient:
    """Mock LLM client returning realistic JSON responses for code authoring."""

    def __init__(self, response_dict: dict[str, Any] | None = None) -> None:
        self.call_count = 0
        self.last_prompt = ""
        self.response_dict = response_dict or {
            "files": {
                "services/order_service.py": (
                    "class OrderService:\n"
                    "    def create_order(self, order_id: str) -> dict:\n"
                    "        return {'status': 'CREATED', 'order_id': order_id}\n"
                )
            },
            "summary": "Implemented OrderService with create_order method.",
            "interfaces": [
                {
                    "symbol_name": "OrderService",
                    "symbol_type": "class",
                    "change_type": "added",
                    "file_path": "services/order_service.py",
                    "signature": "class OrderService",
                    "docstring": "Order processing service.",
                    "is_breaking": False,
                }
            ],
            "dependencies": [],
            "assumptions": ["Order IDs are UUID strings."],
            "unresolved_issues": [],
        }

    async def generate(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        self.call_count += 1
        self.last_prompt = user_prompt
        return self.response_dict


@pytest.fixture
def fake_sandbox() -> FakeSandboxClient:
    return FakeSandboxClient()


@pytest.fixture
def code_agent(fake_sandbox: FakeSandboxClient) -> CodeImplementationAgent:
    return CodeImplementationAgent(sandbox_client=fake_sandbox)


@pytest.fixture
def valid_grant() -> DevelopmentTaskGrant:
    return DevelopmentTaskGrant(
        task_id="task-code-001",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        component_name="OrderProcessor",
        target_files=["services/order_service.py"],
        allowed_operations=["generate_diff", "ast_validate", "lint"],
        sandbox_capabilities=[SandboxCapability.CODE.value],
        tool_permissions=["ast_parser", "code_linter", "code_patcher"],
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )


@pytest.fixture
def valid_plan() -> DevelopmentPlan:
    return DevelopmentPlan(
        plan_id="plan-code-001",
        task_id="task-code-001",
        workflow_id="wf-dev-001",
        objective="Implement order processing business logic",
        affected_files=["services/order_service.py"],
        steps=[
            DevelopmentPlanStep(
                step_id="step-ui-001",
                subagent_id="DEV-UI",
                status="REQUIRED",
                description="UI Layout",
                affected_artifacts=["templates/order.html"],
            ),
            DevelopmentPlanStep(
                step_id="step-code-001",
                subagent_id="DEV-CODE",
                status="REQUIRED",
                description="Application Code",
                affected_artifacts=["services/order_service.py"],
            ),
        ],
    )


@pytest.mark.asyncio
async def test_code_implementation_success(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-CODE executes successfully within plan authority producing sealed deliverable."""
    candidate = await code_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )

    assert isinstance(candidate, CodeCandidateDeliverable)
    assert candidate.task_id == valid_grant.task_id
    assert "services/order_service.py" in candidate.changed_files
    assert len(candidate.code_diffs) == 1
    assert candidate.code_diffs[0].file_path == "services/order_service.py"
    assert candidate.sanity_check_result.is_valid is True
    assert candidate.sanity_check_result.compiler_passed is True
    assert candidate.candidate_hash != ""
    assert len(candidate.candidate_hash) == 64
    assert len(candidate.commands_tool_evidence) >= 4  # patch, format, ast, compile


@pytest.mark.asyncio
async def test_plan_authority_enforced_fails_if_skipped(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """DEV-CODE fails closed if marked SKIPPED_NOT_APPLICABLE in approved plan."""
    skipped_plan = DevelopmentPlan(
        plan_id="plan-skip-code",
        task_id=valid_grant.task_id,
        workflow_id="wf-test-01",
        objective="Only frontend changes",
        affected_files=["templates/order.html"],
        steps=[
            DevelopmentPlanStep(
                step_id="step-code",
                subagent_id="DEV-CODE",
                status="SKIPPED_NOT_APPLICABLE",
                skip_reason="No backend business logic required for this release.",
            ),
        ],
    )

    with pytest.raises(PolicyViolationError) as exc_info:
        await code_agent.execute_step(
            grant=valid_grant,
            plan=skipped_plan,
            context={"tenant_id": "tenant-alpha"},
        )
    assert "marked SKIPPED_NOT_APPLICABLE" in str(exc_info.value)


@pytest.mark.asyncio
async def test_plan_authority_passes_when_required(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-CODE succeeds when step is required and marked applicable."""
    candidate = await code_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )
    assert candidate.component_name == valid_grant.component_name


@pytest.mark.asyncio
async def test_plan_authority_fails_if_no_step_for_code(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """DEV-CODE fails closed if plan has steps but none for DEV-CODE."""
    plan_no_code = DevelopmentPlan(
        plan_id="plan-no-code",
        task_id=valid_grant.task_id,
        workflow_id="wf-001",
        objective="Only CMS update",
        affected_files=["cms/schema.json"],
        steps=[
            DevelopmentPlanStep(
                step_id="step-cms-001",
                subagent_id="DEV-CMS",
                status="REQUIRED",
                description="CMS Schema",
                affected_artifacts=["cms/schema.json"],
            )
        ],
    )
    with pytest.raises(PolicyViolationError) as exc_info:
        await code_agent.execute_step(
            grant=valid_grant,
            plan=plan_no_code,
            context={"tenant_id": "tenant-alpha"},
        )
    assert "does not contain a step for DEV-CODE" in str(exc_info.value)


@pytest.mark.asyncio
async def test_predecessor_hash_verification_success(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-CODE verifies predecessor hash from UI candidate."""
    ui_candidate = UiCandidateDeliverable(
        candidate_id="cand-ui-123",
        task_id=valid_grant.task_id,
        workflow_id="wf-001",
        component_name="OrderProcessor",
        render_evidence=UiRenderEvidence(
            viewports=[],
            simulated_in_sandbox=True,
            visual_snapshot_hash="vis-hash-123",
        ),
        accessibility_report=UiAccessibilityReport(
            target_standard="WCAG 2.2 A/AA",
            rules_evaluated=6,
            rules_passed=6,
            compliance_score=100.0,
        ),
        validation_evidence=UiValidationEvidence(ast_valid=True),
    )
    ui_hash = ui_candidate.compute_candidate_hash()

    candidate = await code_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        context={
            "tenant_id": "tenant-alpha",
            "ui_candidate": ui_candidate,
            "predecessor_hash": ui_hash,
        },
    )
    assert candidate.predecessor_hash == ui_hash


@pytest.mark.asyncio
async def test_stale_or_invalid_predecessor_hash_rejected(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-CODE fails closed on stale predecessor hash mismatch."""
    with pytest.raises(PolicyViolationError) as exc_info:
        await code_agent.execute_step(
            grant=valid_grant,
            plan=valid_plan,
            context={
                "tenant_id": "tenant-alpha",
                "simulate_stale_predecessor": True,
            },
        )
    assert "Predecessor verification failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_scope_boundary_violation_rejected(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-CODE fails closed if mutation targets unauthorized artifacts."""
    unauthorized_grant = DevelopmentTaskGrant(
        task_id=valid_grant.task_id,
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        component_name="OrderProcessor",
        target_files=["services/unauthorized_analytics.py"],
        allowed_operations=["generate_diff", "ast_validate", "lint"],
        sandbox_capabilities=[SandboxCapability.CODE.value],
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )
    with pytest.raises(PolicyViolationError) as exc_info:
        await code_agent.execute_step(
            grant=unauthorized_grant,
            plan=valid_plan,
            context={"tenant_id": "tenant-alpha"},
        )
    assert "Scope boundary violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tenant_isolation_breach_rejected(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-CODE fails closed on tenant mismatch between context and grant."""
    with pytest.raises(PolicyViolationError) as exc_info:
        await code_agent.execute_step(
            grant=valid_grant,
            plan=valid_plan,
            context={"tenant_id": "tenant-beta"},
        )
    assert "Tenant isolation breach" in str(exc_info.value)


@pytest.mark.asyncio
async def test_unauthorized_dependency_change_rejected(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-CODE fails closed when dependency modification is not authorized by plan."""
    with pytest.raises(PolicyViolationError) as exc_info:
        await code_agent.execute_step(
            grant=valid_grant,
            plan=valid_plan,
            context={
                "tenant_id": "tenant-alpha",
                "requested_dependencies": [
                    {"package_name": "malicious-pkg", "action": "ADD", "version_spec": ">=1.0.0"}
                ],
            },
        )
    assert "not authorized by the approved plan" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authorized_dependency_change_succeeds(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-CODE accepts dependency modification when explicitly authorized by plan."""
    valid_plan.discovered_facts["dependencies_authorized"] = True
    valid_plan.discovered_facts["allowed_dependencies"] = ["pydantic-settings"]

    candidate = await code_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        context={
            "tenant_id": "tenant-alpha",
            "requested_dependencies": [
                {"package_name": "pydantic-settings", "action": "ADD", "version_spec": ">=2.0"}
            ],
        },
    )
    assert len(candidate.dependency_changes) == 1
    assert candidate.dependency_changes[0].package_name == "pydantic-settings"
    assert candidate.dependency_changes[0].is_authorized is True


@pytest.mark.asyncio
async def test_malformed_code_compiler_sanity_failure(
    fake_sandbox: FakeSandboxClient,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Compiler sanity checker catches syntax and compilation errors."""
    bad_llm = FakeLlmClient(
        response_dict={
            "files": {"services/order_service.py": "def broken_syntax(:\n    pass\n"},
            "summary": "Broken syntax implementation",
            "interfaces": [],
            "dependencies": [],
            "assumptions": [],
            "unresolved_issues": [],
        }
    )
    agent = CodeImplementationAgent(sandbox_client=fake_sandbox, llm_client=bad_llm)

    candidate = await agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )
    assert candidate.sanity_check_result.compiler_passed is False
    assert candidate.sanity_check_result.is_valid is False
    assert len(candidate.sanity_check_result.errors) > 0


@pytest.mark.asyncio
async def test_llm_reasoning_integration(
    fake_sandbox: FakeSandboxClient,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-CODE incorporates LLM reasoning for custom methods and interfaces."""
    mock_llm = FakeLlmClient(
        response_dict={
            "files": {
                "services/order_service.py": (
                    "class OrderService:\n"
                    "    async def calculate_discount(self, amount: float) -> float:\n"
                    "        return amount * 0.9\n"
                )
            },
            "summary": "Added calculate_discount method.",
            "interfaces": [
                {
                    "symbol_name": "calculate_discount",
                    "symbol_type": "method",
                    "change_type": "added",
                    "file_path": "services/order_service.py",
                    "signature": "async def calculate_discount(self, amount: float) -> float",
                    "is_breaking": False,
                }
            ],
            "dependencies": [],
            "assumptions": ["Discount rate is fixed."],
            "unresolved_issues": [],
        }
    )
    agent = CodeImplementationAgent(sandbox_client=fake_sandbox, llm_client=mock_llm)

    candidate = await agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )
    assert mock_llm.call_count == 1
    assert len(candidate.contract_interface_changes) == 1
    assert candidate.contract_interface_changes[0].symbol_name == "calculate_discount"


@pytest.mark.asyncio
async def test_deterministic_fallback_without_llm(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-CODE executes deterministic fallback when no LLM is configured."""
    candidate = await code_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )
    assert "OrderProcessorService" in candidate.source_code["services/order_service.py"]
    assert candidate.sanity_check_result.compiler_passed is True


@pytest.mark.asyncio
async def test_rejection_and_revision_attempt_handling(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Rejection generates immutable attempt 2 with reviewer feedback integrated."""
    # Attempt 1
    att1 = await code_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
        attempt_id="att-1",
    )
    assert att1.attempt_id == "att-1"
    att1_hash = att1.candidate_hash

    # Attempt 2 after HITL rejection
    att2 = await code_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
        attempt_id="att-2",
        previous_candidate=att1,
        reviewer_feedback="Please add bounded retry logic for transient database exceptions.",
    )
    assert att2.attempt_id == "att-2"
    assert att2.rejection_feedback == "Please add bounded retry logic for transient database exceptions."
    assert "retry_operation" in att2.source_code["services/order_service.py"]
    assert att2.candidate_hash != att1_hash


@pytest.mark.asyncio
async def test_deterministic_candidate_sealing(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Candidate hash computation is deterministic and stable."""
    cand = await code_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )
    h1 = cand.candidate_hash
    h2 = cand.compute_candidate_hash()
    assert h1 == h2


@pytest.mark.asyncio
async def test_development_agent_execute_code_step_with_provenance(
    fake_sandbox: FakeSandboxClient,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DevelopmentAgent.execute_code_step integrates with ProvenanceRecorder."""
    dev_agent = DevelopmentAgent(sandbox_client=fake_sandbox)
    fake_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repository=fake_repo)

    candidate, cand_hash = await dev_agent.execute_code_step(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
        provenance_recorder=recorder,
    )
    assert candidate.candidate_hash == cand_hash
    tenant_id = valid_grant.tenant_scope.tenant_id
    events = fake_repo._chains.get(tenant_id, [])
    assert len(events) >= 1
    code_event = [e for e in events if e.agent == "DEV-CODE"][0]
    assert code_event.tenant_id == tenant_id
    assert code_event.metadata["candidate_hash"] == cand_hash


def test_sandbox_micro_tools_code_operations() -> None:
    """Direct invocation of execute_s_code for all DEV-CODE micro-tool operations."""
    # 1. apply_code_patch
    patch_res = execute_s_code(
        operation="apply_code_patch",
        payload={
            "target_file": "services/auth.py",
            "new_content": "def authenticate():\n    return True\n",
            "allowed_artifacts": ["services/auth.py"],
        },
    )
    assert patch_res["is_patched"] is True
    assert "authenticate" in patch_res["patched_content"]

    # Scope boundary violation in micro-tool
    bad_scope = execute_s_code(
        operation="apply_code_patch",
        payload={
            "target_file": "sensitive/keys.py",
            "new_content": "SECRET=1",
            "allowed_artifacts": ["services/auth.py"],
        },
    )
    assert bad_scope["status"] == "security_violation"

    # Path traversal rejection
    bad_path = execute_s_code(
        operation="apply_code_patch",
        payload={"target_file": "../etc/passwd", "new_content": "root"},
    )
    assert bad_path["status"] == "security_violation"

    # 2. format_code
    fmt_res = execute_s_code(
        operation="format_code",
        payload={
            "file_path": "services/auth.py",
            "code": "def authenticate(  ):\n    return    True\n",
        },
    )
    assert fmt_res["is_formatted"] is True

    # 3. inspect_ast_symbols
    ast_res = execute_s_code(
        operation="inspect_ast_symbols",
        payload={
            "file_path": "services/auth.py",
            "code": "class Auth:\n    def login(self):\n        pass\n",
        },
    )
    assert ast_res["ast_valid"] is True
    assert "Auth" in ast_res["symbols_summary"]["classes"]

    # 4. validate_syntax_compiler
    sanity_res = execute_s_code(
        operation="validate_syntax_compiler",
        payload={
            "file_path": "services/auth.py",
            "code": "class Auth:\n    pass\n",
        },
    )
    assert sanity_res["is_valid"] is True
    assert sanity_res["compiler_passed"] is True

    # Syntax failure in compiler check
    broken_sanity = execute_s_code(
        operation="validate_syntax_compiler",
        payload={
            "file_path": "services/auth.py",
            "code": "class Auth: def (:\n",
        },
    )
    assert broken_sanity["is_valid"] is False
    assert broken_sanity["compiler_passed"] is False

    # 5. manage_packages (unauthorized)
    unauth_pkg = execute_s_code(
        operation="manage_packages",
        payload={"package_name": "unauthorized-pkg", "egress_granted": False},
    )
    assert unauth_pkg["status"] == "security_violation"

    # manage_packages (authorized with egress)
    auth_pkg = execute_s_code(
        operation="manage_packages",
        payload={
            "package_name": "pydantic",
            "action": "ADD",
            "egress_granted": True,
            "is_plan_authorized": True,
        },
    )
    assert auth_pkg["is_authorized"] is True


@pytest.mark.asyncio
async def test_hitl_handoff_and_to_development_deliverable(
    code_agent: CodeImplementationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Candidate deliverable converts cleanly to DevelopmentDeliverable for HITL review."""
    candidate = await code_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )
    dev_deliverable = candidate.to_development_deliverable(tenant_id="tenant-alpha")
    assert dev_deliverable.deliverable_id == candidate.candidate_id
    assert dev_deliverable.component_name == candidate.component_name
    assert len(dev_deliverable.code_diffs) == 1
    assert dev_deliverable.security_checks_passed is True
