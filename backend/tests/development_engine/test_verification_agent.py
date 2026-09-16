"""Comprehensive unit and integration tests for Task DE-10: DEV-VERIFY.

Validates:
1. Clean pass: All checks pass cleanly -> VerificationVerdict.PASS.
2. Missing candidate fail-closed: Candidate=None raises PolicyViolationError.
3. Digest mismatch fail-closed: Stale or mismatched expected_candidate_hash fails closed.
4. Plan authority enforcement: DEV-VERIFY marked SKIPPED raises PolicyViolationError.
5. Build failure verdict: Compilation error yields outcome=FAIL, verdict=FAIL, routes remediation.
6. Lint check failure verdict: Check-only lint failure yields outcome=FAIL, verdict=FAIL.
7. Format check failure verdict: Check-only format failure yields outcome=FAIL.
8. Type check failure verdict: Type violations yield outcome=FAIL, verdict=FAIL.
9. Automated tests failure verdict: Test failures yield outcome=FAIL, test totals populated.
10. Coverage threshold failure: Coverage below minimum required threshold yields outcome=FAIL.
11. Blocked environment: Missing tools or failed isolation yields verdict=BLOCKED.
12. Read-only invariance: Mutation or auto-fix requests fail closed with PolicyViolationError.
13. Author sub-agent remediation routing for DEV-UI: Fails route to DEV-UI.
14. Author sub-agent remediation routing for DEV-CMS: Fails route to DEV-CMS.
15. Deterministic dossier hashing: canonical_bytes and compute_dossier_hash are deterministic.
16. DevelopmentAgent integration: execute_verify_step records provenance and returns dossier.
17. State machine transition guards: Machine DENY + human APPROVE blocked fail-closed.
18. Direct micro_tools execution: All verification operations in execute_s_code tested directly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.development_engine.development import DevelopmentAgent
from app.agents.development_engine.subagents.verification import VerificationAgent
from app.core.exceptions import PolicyViolationError
from app.integrations.sandbox.micro_tools import execute_s_code
from app.orchestration.development_state_machine import DevelopmentStateMachine
from app.schemas.agent_contracts import CodeDiffEntry
from app.schemas.cms import (
    CmsCandidateDeliverable,
    CmsChangeClassification,
    CmsCompatibilityReport,
    CmsContentModelSchema,
    CmsValidationEvidence,
)
from app.schemas.development import (
    CheckOutcome,
    CodeCandidateDeliverable,
    CodeSanityCheckResult,
    DevelopmentApprovalToken,
    DevelopmentPlan,
    DevelopmentPlanStep,
    DevelopmentTaskGrant,
    TestTotals,
    VerificationCheckResult,
    VerificationDossier,
    VerificationVerdict,
)
from app.schemas.development.ui import (
    UiAccessibilityReport,
    UiCandidateDeliverable,
    UiRenderEvidence,
    UiValidationEvidence,
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
def verify_agent(fake_sandbox: FakeSandboxClient) -> VerificationAgent:
    return VerificationAgent(sandbox_client=fake_sandbox)


@pytest.fixture
def valid_grant() -> DevelopmentTaskGrant:
    return DevelopmentTaskGrant(
        task_id="task-verif-001",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-beta"),
        component_name="PaymentService",
        target_files=["services/payment_service.py"],
        allowed_operations=[
            "verify_environment",
            "run_build",
            "run_lint_check",
            "run_format_check",
            "run_type_check",
            "run_automated_tests",
            "run_coverage_analysis",
        ],
        sandbox_capabilities=[SandboxCapability.CODE.value],
        tool_permissions=[
            "environment_verifier",
            "build_runner",
            "lint_checker",
            "format_checker",
            "type_checker",
            "test_runner",
            "coverage_analyzer",
        ],
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )


@pytest.fixture
def valid_plan() -> DevelopmentPlan:
    return DevelopmentPlan(
        plan_id="plan-verif-001",
        task_id="task-verif-001",
        workflow_id="wf-verif-001",
        objective="Verify PaymentService implementation",
        affected_files=["services/payment_service.py"],
        steps=[
            DevelopmentPlanStep(
                step_id="step-code-001",
                subagent_id="DEV-CODE",
                status="REQUIRED",
                description="Application Code Implementation",
                affected_artifacts=["services/payment_service.py"],
            ),
            DevelopmentPlanStep(
                step_id="step-verif-001",
                subagent_id="DEV-VERIFY",
                status="REQUIRED",
                description="Independent Technical Verification",
                affected_artifacts=["services/payment_service.py"],
            ),
        ],
    )


@pytest.fixture
def sample_code_candidate() -> CodeCandidateDeliverable:
    candidate = CodeCandidateDeliverable(
        candidate_id="cand-code-12345",
        task_id="task-verif-001",
        workflow_id="wf-verif-001",
        attempt_id="att-1",
        component_name="PaymentService",
        changed_files=["services/payment_service.py"],
        code_diffs=[
            CodeDiffEntry(
                file_path="services/payment_service.py",
                diff_unified=(
                    "--- a/services/payment_service.py\n"
                    "+++ b/services/payment_service.py\n"
                    "@@ -0,0 +1,10 @@\n"
                    "+class PaymentService:\n"
                    "+    def process_payment(self, amount: float) -> bool:\n"
                    "+        return amount > 0\n"
                ),
                action="modify",
            )
        ],
        source_code={
            "services/payment_service.py": (
                "class PaymentService:\n"
                "    def process_payment(self, amount: float) -> bool:\n"
                "        return amount > 0\n"
            )
        },
        implementation_summary="Implemented PaymentService logic.",
        sanity_check_result=CodeSanityCheckResult(
            is_valid=True,
            syntax_valid=True,
            compiler_passed=True,
            checks_run=["ast_parse", "compiler_exec"],
        ),
    )
    candidate.compute_candidate_hash()
    return candidate


@pytest.mark.asyncio
async def test_verification_clean_pass(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """DEV-VERIFY runs all checks cleanly, producing a sealed PASS dossier."""
    dossier = await verify_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        candidate=sample_code_candidate,
        expected_candidate_hash=sample_code_candidate.candidate_hash,
    )

    assert isinstance(dossier, VerificationDossier)
    assert dossier.verdict == VerificationVerdict.PASS
    assert dossier.is_acceptable_for_dev_sec() is True
    assert dossier.remediation_step is None
    assert dossier.candidate_hash == sample_code_candidate.candidate_hash
    assert len(dossier.checks) == 7
    assert all(c.outcome == CheckOutcome.PASS for c in dossier.checks)
    assert dossier.test_totals.passed > 0
    assert dossier.test_totals.failed == 0
    assert dossier.coverage_report is not None
    assert dossier.coverage_report.coverage_threshold_met is True
    assert len(dossier.dossier_hash) == 64


@pytest.mark.asyncio
async def test_verification_fails_closed_missing_candidate(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-VERIFY fails closed when candidate deliverable is missing."""
    with pytest.raises(PolicyViolationError, match="Candidate deliverable is missing"):
        await verify_agent.execute_step(
            grant=valid_grant,
            plan=valid_plan,
            candidate=None,
        )


@pytest.mark.asyncio
async def test_verification_fails_closed_digest_mismatch(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """DEV-VERIFY fails closed when expected candidate hash does not match actual hash."""
    with pytest.raises(PolicyViolationError, match="Candidate digest mismatch"):
        await verify_agent.execute_step(
            grant=valid_grant,
            plan=valid_plan,
            candidate=sample_code_candidate,
            expected_candidate_hash="0000000000000000000000000000000000000000000000000000000000000000",
        )


@pytest.mark.asyncio
async def test_verification_plan_authority_enforced(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """DEV-VERIFY rejects execution if DEV-VERIFY step is marked SKIPPED_NOT_APPLICABLE in plan."""
    skipped_plan = DevelopmentPlan(
        plan_id="plan-skipped-001",
        task_id="task-verif-001",
        workflow_id="wf-verif-001",
        objective="Verify with skipped verify step",
        affected_files=["services/payment_service.py"],
        steps=[
            DevelopmentPlanStep(
                step_id="step-verif-001",
                subagent_id="DEV-VERIFY",
                status="SKIPPED_NOT_APPLICABLE",
                skip_reason="Verification bypassed by user",
                description="Verification step",
                affected_artifacts=["services/payment_service.py"],
            ),
        ],
    )

    with pytest.raises(PolicyViolationError, match="Execution of DEV-VERIFY is not authorized"):
        await verify_agent.execute_step(
            grant=valid_grant,
            plan=skipped_plan,
            candidate=sample_code_candidate,
            expected_candidate_hash=sample_code_candidate.candidate_hash,
        )


@pytest.mark.asyncio
async def test_verification_build_failure_verdict(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """Build failure triggers FAIL verdict and routes remediation to DEV-CODE."""
    dossier = await verify_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        candidate=sample_code_candidate,
        expected_candidate_hash=sample_code_candidate.candidate_hash,
        context={"simulate_build_failure": "SyntaxError: unexpected EOF while parsing"},
    )

    assert dossier.verdict == VerificationVerdict.FAIL
    assert dossier.is_acceptable_for_dev_sec() is False
    assert dossier.remediation_step == "DEV-CODE"

    build_check = next(c for c in dossier.checks if c.check_type == "build")
    assert build_check.outcome == CheckOutcome.FAIL
    assert "SyntaxError" in build_check.failure_reasons[0]


@pytest.mark.asyncio
async def test_verification_lint_failure_verdict(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """Lint check failure yields outcome=FAIL and routes remediation to DEV-CODE."""
    dossier = await verify_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        candidate=sample_code_candidate,
        expected_candidate_hash=sample_code_candidate.candidate_hash,
        context={
            "simulate_lint_errors": [
                "services/payment_service.py:1: [F401] 'os' imported but unused"
            ]
        },
    )

    assert dossier.verdict == VerificationVerdict.FAIL
    assert dossier.remediation_step == "DEV-CODE"

    lint_check = next(c for c in dossier.checks if c.check_type == "lint")
    assert lint_check.outcome == CheckOutcome.FAIL
    assert lint_check.error_count == 1


@pytest.mark.asyncio
async def test_verification_format_failure_verdict(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """Format check-only failure triggers FAIL verdict without modifying candidate files."""
    original_code = sample_code_candidate.source_code["services/payment_service.py"]

    dossier = await verify_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        candidate=sample_code_candidate,
        expected_candidate_hash=sample_code_candidate.candidate_hash,
        context={"simulate_unformatted_files": ["services/payment_service.py"]},
    )

    assert dossier.verdict == VerificationVerdict.FAIL
    assert dossier.remediation_step == "DEV-CODE"
    fmt_check = next(c for c in dossier.checks if c.check_type == "format")
    assert fmt_check.outcome == CheckOutcome.FAIL

    # Invariance check: candidate source code was not touched
    assert sample_code_candidate.source_code["services/payment_service.py"] == original_code


@pytest.mark.asyncio
async def test_verification_type_failure_verdict(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """Type check failure triggers FAIL verdict."""
    dossier = await verify_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        candidate=sample_code_candidate,
        expected_candidate_hash=sample_code_candidate.candidate_hash,
        context={
            "simulate_type_errors": [
                "services/payment_service.py:2: Incompatible return type (got float, expected bool)"
            ]
        },
    )

    assert dossier.verdict == VerificationVerdict.FAIL
    type_check = next(c for c in dossier.checks if c.check_type == "type_check")
    assert type_check.outcome == CheckOutcome.FAIL
    assert type_check.error_count == 1


@pytest.mark.asyncio
async def test_verification_automated_tests_failure_verdict(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """Automated test failures yield outcome=FAIL and populate structured test totals."""
    dossier = await verify_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        candidate=sample_code_candidate,
        expected_candidate_hash=sample_code_candidate.candidate_hash,
        context={
            "simulate_test_results": {
                "passed": 8,
                "failed": 2,
                "skipped": 1,
                "errored": 0,
                "duration_s": 1.45,
                "failures": [
                    "test_process_payment_negative FAILED",
                    "test_process_payment_zero FAILED",
                ],
            }
        },
    )

    assert dossier.verdict == VerificationVerdict.FAIL
    assert dossier.test_totals.passed == 8
    assert dossier.test_totals.failed == 2
    assert dossier.test_totals.skipped == 1
    assert dossier.test_totals.total == 11
    assert dossier.remediation_step == "DEV-CODE"

    unit_check = next(c for c in dossier.checks if c.check_type == "unit_test")
    assert unit_check.outcome == CheckOutcome.FAIL
    assert len(unit_check.failure_reasons) == 2


@pytest.mark.asyncio
async def test_verification_coverage_threshold_failure(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """Coverage below configured threshold (e.g. 70% < 80%) yields FAIL verdict."""
    dossier = await verify_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        candidate=sample_code_candidate,
        expected_candidate_hash=sample_code_candidate.candidate_hash,
        context={
            "minimum_required_pct": 80.0,
            "simulate_coverage": {
                "line_coverage_pct": 68.5,
                "branch_coverage_pct": 60.0,
                "total_statements": 100,
                "covered_statements": 68,
                "missing_lines_by_file": {"services/payment_service.py": [5, 6, 7]},
            },
        },
    )

    assert dossier.verdict == VerificationVerdict.FAIL
    assert dossier.coverage_report is not None
    assert dossier.coverage_report.coverage_threshold_met is False
    assert dossier.coverage_report.line_coverage_pct == 68.5

    cov_check = next(c for c in dossier.checks if c.check_type == "coverage")
    assert cov_check.outcome == CheckOutcome.FAIL


@pytest.mark.asyncio
async def test_verification_blocked_environment(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """Missing tool or broken sandbox isolation yields BLOCKED verdict immediately."""
    dossier = await verify_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        candidate=sample_code_candidate,
        expected_candidate_hash=sample_code_candidate.candidate_hash,
        context={"tool_missing_pytest": True},
    )

    assert dossier.verdict == VerificationVerdict.BLOCKED
    assert dossier.is_acceptable_for_dev_sec() is False
    assert len(dossier.checks) == 1
    assert dossier.checks[0].outcome == CheckOutcome.ERROR


@pytest.mark.asyncio
async def test_verification_read_only_invariance_rejects_mutation(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """DEV-VERIFY strictly rejects auto-fix or mutation requests fail-closed."""
    with pytest.raises(PolicyViolationError, match="strictly read-only"):
        await verify_agent.execute_step(
            grant=valid_grant,
            plan=valid_plan,
            candidate=sample_code_candidate,
            expected_candidate_hash=sample_code_candidate.candidate_hash,
            context={"auto_fix": True},
        )


@pytest.mark.asyncio
async def test_verification_ui_candidate_remediation_routing(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Failure verifying a UiCandidateDeliverable routes remediation to DEV-UI."""
    ui_candidate = UiCandidateDeliverable(
        candidate_id="cand-ui-12345",
        task_id="task-verif-001",
        workflow_id="wf-verif-001",
        component_name="PaymentForm",
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

    dossier = await verify_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        candidate=ui_candidate,
        expected_candidate_hash=ui_hash,
        context={"simulate_lint_errors": ["templates/payment_form.html:1: Unclosed tag"]},
    )

    assert dossier.verdict == VerificationVerdict.FAIL
    assert dossier.remediation_step == "DEV-UI"


@pytest.mark.asyncio
async def test_verification_cms_candidate_remediation_routing(
    verify_agent: VerificationAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Failure verifying a CmsCandidateDeliverable routes remediation to DEV-CMS."""
    cms_candidate = CmsCandidateDeliverable(
        candidate_id="cand-cms-12345",
        task_id="task-verif-001",
        workflow_id="wf-verif-001",
        schemas=[
            CmsContentModelSchema(
                model_name="PaymentPlan",
                fields=[],
            )
        ],
        compatibility_report=CmsCompatibilityReport(
            is_compatible=True, classification=CmsChangeClassification.ADDITIVE
        ),
        validation_evidence=CmsValidationEvidence(ast_valid=True, simulated_success=True),
        subagent="DEV-CMS",
    )
    cms_hash = cms_candidate.compute_candidate_hash()

    dossier = await verify_agent.execute_step(
        grant=valid_grant,
        plan=valid_plan,
        candidate=cms_candidate,
        expected_candidate_hash=cms_hash,
        context={"simulate_build_failure": "Schema migration conflict in PaymentPlan"},
    )

    assert dossier.verdict == VerificationVerdict.FAIL
    assert dossier.remediation_step == "DEV-CMS"


def test_deterministic_dossier_hashing(sample_code_candidate: CodeCandidateDeliverable) -> None:
    """VerificationDossier canonical byte representation and hashing are deterministic."""
    check = VerificationCheckResult(
        check_id="chk-01",
        check_type="lint",
        outcome=CheckOutcome.PASS,
        command_or_operation="run_lint_check",
        exit_code=0,
    )
    dossier1 = VerificationDossier(
        dossier_id="dos-deterministic-001",
        task_id="task-verif-001",
        workflow_id="wf-verif-001",
        candidate_hash=sample_code_candidate.candidate_hash,
        target_candidate_id=sample_code_candidate.candidate_id,
        component_name=sample_code_candidate.component_name,
        verdict=VerificationVerdict.PASS,
        checks=[check],
        test_totals=TestTotals(passed=10, failed=0, total=10),
    )
    h1 = dossier1.compute_dossier_hash()

    dossier2 = VerificationDossier(
        dossier_id="dos-deterministic-001",
        task_id="task-verif-001",
        workflow_id="wf-verif-001",
        candidate_hash=sample_code_candidate.candidate_hash,
        target_candidate_id=sample_code_candidate.candidate_id,
        component_name=sample_code_candidate.component_name,
        verdict=VerificationVerdict.PASS,
        checks=[check],
        test_totals=TestTotals(passed=10, failed=0, total=10),
    )
    h2 = dossier2.compute_dossier_hash()

    assert h1 == h2
    assert len(h1) == 64


@pytest.mark.asyncio
async def test_development_agent_execute_verify_step_with_provenance(
    fake_sandbox: FakeSandboxClient,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
    sample_code_candidate: CodeCandidateDeliverable,
) -> None:
    """DevelopmentAgent.execute_verify_step records provenance for DEV-VERIFY."""
    agent = DevelopmentAgent(sandbox_client=fake_sandbox)
    fake_repo = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(fake_repo)

    dossier = await agent.execute_verify_step(
        grant=valid_grant,
        candidate=sample_code_candidate,
        expected_candidate_hash=sample_code_candidate.candidate_hash,
        plan=valid_plan,
        workflow_id="wf-verif-001",
        provenance_recorder=provenance_recorder,
    )

    assert isinstance(dossier, VerificationDossier)
    assert dossier.verdict == VerificationVerdict.PASS

    records = fake_repo._chains.get("tenant-beta", [])
    verify_records = [r for r in records if r.agent == "DEV-VERIFY"]
    assert len(verify_records) == 1
    assert verify_records[0].metadata["verdict"] == "PASS"
    assert verify_records[0].metadata["dossier_hash"] == dossier.dossier_hash


def test_state_machine_transition_guards_for_verification() -> None:
    """State machine transition guards enforce machine verdict precedence over human approval."""
    sm = DevelopmentStateMachine()

    # Case 1: Machine PASS + Human APPROVE -> Transition to APPROVED succeeds
    pass_dossier = VerificationDossier(
        dossier_id="dos-pass-001",
        task_id="task-sm-001",
        workflow_id="wf-sm-001",
        candidate_hash="hash-12345",
        target_candidate_id="cand-001",
        component_name="PaymentService",
        verdict=VerificationVerdict.PASS,
    )
    pass_dossier.compute_dossier_hash()

    token = DevelopmentApprovalToken(
        token_id="tok-001",
        task_id="task-sm-001",
        workflow_id="wf-sm-001",
        step_id="step-verif-001",
        attempt_id="att-1",
        subagent_id="DEV-VERIFY",
        decision="APPROVE",
        input_snapshot_hash="hash-in-12345",
        output_snapshot_hash=pass_dossier.dossier_hash,
        review_dossier_hash=pass_dossier.dossier_hash,
        reviewer_identity="reviewer-alice",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revision_notes="Approved technical verification.",
    )

    sm.validate_transition_guards(
        current_state=DevelopmentWorkflowState.HITL_PENDING,
        target_state=DevelopmentWorkflowState.APPROVED,
        step_id="step-verif-001",
        attempt_id="att-1",
        state_data={
            "approval_token": token,
            "verification_dossier": pass_dossier,
            "machine_policy_allowed": True,
        },
    )

    # Case 2: Machine FAIL + Human APPROVE -> Transition to APPROVED BLOCKED fail-closed
    fail_dossier = VerificationDossier(
        dossier_id="dos-fail-001",
        task_id="task-sm-001",
        workflow_id="wf-sm-001",
        candidate_hash="hash-12345",
        target_candidate_id="cand-001",
        component_name="PaymentService",
        verdict=VerificationVerdict.FAIL,
        remediation_step="DEV-CODE",
    )
    fail_dossier.compute_dossier_hash()

    with pytest.raises(PolicyViolationError, match="must be 'PASS' to advance to DEV-SEC"):
        sm.validate_transition_guards(
            current_state=DevelopmentWorkflowState.HITL_PENDING,
            target_state=DevelopmentWorkflowState.APPROVED,
            step_id="step-verif-001",
            attempt_id="att-1",
            state_data={
                "approval_token": token,
                "verification_dossier": fail_dossier,
            },
        )


def test_direct_micro_tools_verification_dispatch() -> None:
    """Direct sandbox micro_tools execution for all DEV-VERIFY operations in S_CODE."""
    code_source = {"module.py": "def add(a: int, b: int) -> int:\n    return a + b\n"}

    # 1. verify_environment
    env_res = execute_s_code(
        operation="verify_environment",
        payload={"required_tools": ["python", "pytest"]},
    )
    assert env_res.get("is_ready") is True

    # 2. run_build
    build_res = execute_s_code(
        operation="run_build",
        payload={"source_code": code_source},
    )
    assert build_res.get("build_passed") is True

    # 3. run_lint_check
    lint_res = execute_s_code(
        operation="run_lint_check",
        payload={"source_code": code_source},
    )
    assert lint_res.get("lint_passed") is True

    # 4. run_format_check
    fmt_res = execute_s_code(
        operation="run_format_check",
        payload={"source_code": code_source},
    )
    assert fmt_res.get("format_passed") is True

    # 5. run_type_check
    type_res = execute_s_code(
        operation="run_type_check",
        payload={"source_code": code_source},
    )
    assert type_res.get("type_check_passed") is True

    # 6. run_automated_tests
    test_res = execute_s_code(
        operation="run_automated_tests",
        payload={"tests_passed": 15, "tests_failed": 0},
    )
    assert test_res.get("all_passed") is True
    assert test_res.get("test_totals", {}).get("passed") == 15

    # 7. run_coverage_analysis
    cov_res = execute_s_code(
        operation="run_coverage_analysis",
        payload={"line_coverage_pct": 89.0, "minimum_required_pct": 80.0},
    )
    assert cov_res.get("coverage_threshold_met") is True

    # 8. Mutation attempt rejected fail-closed
    mut_res = execute_s_code(
        operation="run_format_check",
        payload={"source_code": code_source, "mutation_attempted": True},
    )
    assert mut_res.get("security_violation") is True
    assert mut_res.get("mutation_rejected") is True
