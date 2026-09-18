"""Comprehensive unit and integration tests for Task DE-11: DEV-SEC Sub-Agent.

Validates:
1. Clean pass: Candidate with clean code passes all 6 security scans -> SecurityVerdict.PASS.
2. Missing candidate & dossier fail-closed: Both None raises PolicyViolationError.
3. Verification prerequisite check: Candidate that failed DE-10 technical verification rejected.
4. Candidate digest mismatch fail-closed: Digest mismatch raises PolicyViolationError.
5. Expected candidate hash mismatch fail-closed: Stale expected hash raises PolicyViolationError.
6. Plan authority enforcement: DEV-SEC marked SKIPPED raises PolicyViolationError.
7. Read-only invariance: Mutation or auto-fix requests fail closed with PolicyViolationError.
8. SAST dangerous pattern detection: eval/exec/os.system yields CRITICAL hard-block finding, DENY.
9. Secret exposure detection: AWS key / private key yields CRITICAL/HIGH hard-block finding, DENY.
10. SCA dependency vulnerability detection: Vulnerable package yields HIGH hard-block finding, DENY.
11. Config manifest review: DEBUG=True / privileged container yields hard-block finding, DENY.
12. Boundary check: Unauthenticated route yields hard-block finding, DENY.
13. AST introspection pattern: __globals__ attribute yields CRITICAL finding, DENY.
14. Deterministic dossier hashing: canonical_bytes and compute_dossier_hash are deterministic.
15. DevelopmentAgent integration: execute_security_step records provenance and returns dossier.
16. Direct micro_tools execution: All 6 security operations in execute_s_code tested directly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.development_engine.development import DevelopmentAgent
from app.agents.development_engine.subagents.security_review import SecurityReviewAgent
from app.core.exceptions import PolicyViolationError
from app.integrations.sandbox.micro_tools import execute_s_code
from app.schemas.development import (
    CheckOutcome,
    CodeCandidateDeliverable,
    CodeSanityCheckResult,
    DevelopmentPlan,
    DevelopmentPlanStep,
    DevelopmentTaskGrant,
    SecurityCategory,
    SecurityDossier,
    SecuritySeverity,
    SecurityVerdict,
    TestTotals,
    VerificationCheckResult,
    VerificationDossier,
    VerificationVerdict,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository, FakeSandboxClient


@pytest.fixture
def fake_sandbox() -> FakeSandboxClient:
    return FakeSandboxClient()


@pytest.fixture
def sec_agent(fake_sandbox: FakeSandboxClient) -> SecurityReviewAgent:
    return SecurityReviewAgent(sandbox_client=fake_sandbox)


@pytest.fixture
def valid_grant() -> DevelopmentTaskGrant:
    return DevelopmentTaskGrant(
        task_id="task-sec-001",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-beta"),
        component_name="PaymentService",
        target_files=["services/payment_service.py"],
        allowed_operations=[
            "scan_sast",
            "scan_secrets",
            "scan_dependencies_sca",
            "review_manifest_configs",
            "check_authorization_boundaries",
            "analyze_ast_dangerous_patterns",
        ],
        sandbox_capabilities=[SandboxCapability.CODE.value],
        tool_permissions=[
            "sast_scanner",
            "secret_detector",
            "sca_scanner",
            "config_reviewer",
            "boundary_checker",
            "ast_pattern_analyzer",
        ],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


@pytest.fixture
def clean_candidate() -> CodeCandidateDeliverable:
    candidate = CodeCandidateDeliverable(
        candidate_id="cand-pay-001",
        task_id="task-sec-001",
        workflow_id="wf-sec-001",
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
def passed_verification_dossier(clean_candidate: CodeCandidateDeliverable) -> VerificationDossier:
    dossier = VerificationDossier(
        dossier_id="verif-dossier-001",
        task_id="task-sec-001",
        workflow_id="wf-verif-001",
        candidate_hash=clean_candidate.candidate_hash,
        target_candidate_id=clean_candidate.candidate_id,
        component_name="PaymentService",
        verdict=VerificationVerdict.PASS,
        checks=[
            VerificationCheckResult(
                check_id="chk-1",
                check_type="build",
                command_or_operation="run_build",
                outcome=CheckOutcome.PASS,
                exit_code=0,
            )
        ],
        test_totals=TestTotals(total=10, passed=10, failed=0),
    )
    dossier.compute_dossier_hash()
    return dossier


@pytest.mark.asyncio
async def test_security_clean_pass(
    sec_agent: SecurityReviewAgent,
    clean_candidate: CodeCandidateDeliverable,
    passed_verification_dossier: VerificationDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 1: Clean code passes all 6 security scans -> SecurityVerdict.PASS."""
    dossier = await sec_agent.review_security(
        tenant_id="tenant-beta",
        task_id="task-sec-001",
        candidate=clean_candidate,
        verification_dossier=passed_verification_dossier,
        task_grant=valid_grant,
    )

    assert isinstance(dossier, SecurityDossier)
    assert dossier.verdict == SecurityVerdict.PASS
    assert dossier.hard_block_count == 0
    assert len(dossier.findings) == 0
    assert dossier.candidate_hash == clean_candidate.candidate_hash
    assert dossier.dossier_hash != ""
    assert dossier.is_acceptable_for_release() is True
    assert len(dossier.scanners_run) == 6


@pytest.mark.asyncio
async def test_missing_candidate_and_dossier_fails_closed(
    sec_agent: SecurityReviewAgent,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 2: When both candidate and verification dossier are missing, fails closed."""
    with pytest.raises(
        PolicyViolationError,
        match="Neither candidate deliverable nor verification",
    ):
        await sec_agent.review_security(
            tenant_id="tenant-beta",
            task_id="task-sec-001",
            candidate=None,
            verification_dossier=None,
            task_grant=valid_grant,
        )


@pytest.mark.asyncio
async def test_verification_dossier_failed_fails_closed(
    sec_agent: SecurityReviewAgent,
    clean_candidate: CodeCandidateDeliverable,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 3: If candidate failed DE-10 verification, DEV-SEC rejects fail-closed."""
    failed_dossier = VerificationDossier(
        dossier_id="verif-dossier-fail",
        task_id="task-sec-001",
        workflow_id="wf-verif-fail",
        candidate_hash=clean_candidate.candidate_hash,
        target_candidate_id=clean_candidate.candidate_id,
        component_name="PaymentService",
        verdict=VerificationVerdict.FAIL,
    )
    failed_dossier.compute_dossier_hash()

    with pytest.raises(PolicyViolationError, match="DE-10 PASS is strictly required"):
        await sec_agent.review_security(
            tenant_id="tenant-beta",
            task_id="task-sec-001",
            candidate=clean_candidate,
            verification_dossier=failed_dossier,
            task_grant=valid_grant,
        )


@pytest.mark.asyncio
async def test_candidate_digest_mismatch_fails_closed(
    sec_agent: SecurityReviewAgent,
    clean_candidate: CodeCandidateDeliverable,
    passed_verification_dossier: VerificationDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 4: Candidate hash mismatching verification dossier hash fails closed."""
    passed_verification_dossier.candidate_hash = "mismatched-hash-value"

    with pytest.raises(PolicyViolationError, match="Candidate digest mismatch"):
        await sec_agent.review_security(
            tenant_id="tenant-beta",
            task_id="task-sec-001",
            candidate=clean_candidate,
            verification_dossier=passed_verification_dossier,
            task_grant=valid_grant,
        )


@pytest.mark.asyncio
async def test_expected_candidate_hash_mismatch_fails_closed(
    sec_agent: SecurityReviewAgent,
    clean_candidate: CodeCandidateDeliverable,
    passed_verification_dossier: VerificationDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 5: Stale or mismatched expected_candidate_hash fails closed."""
    with pytest.raises(PolicyViolationError, match="Snapshot integrity compromised"):
        await sec_agent.review_security(
            tenant_id="tenant-beta",
            task_id="task-sec-001",
            candidate=clean_candidate,
            verification_dossier=passed_verification_dossier,
            expected_candidate_hash="sha256-different-digest",
            task_grant=valid_grant,
        )


@pytest.mark.asyncio
async def test_plan_authority_enforcement_skipped_fails_closed(
    sec_agent: SecurityReviewAgent,
    clean_candidate: CodeCandidateDeliverable,
    passed_verification_dossier: VerificationDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 6: DEV-SEC marked SKIPPED_NOT_APPLICABLE in plan fails closed."""
    plan = DevelopmentPlan(
        plan_id="plan-001",
        task_id="task-sec-001",
        workflow_id="wf-sec-001",
        objective="Payment Implementation",
        affected_files=["services/payment_service.py"],
        steps=[
            DevelopmentPlanStep(
                step_id="step-sec-001",
                subagent_id="DEV-SEC",
                status="SKIPPED_NOT_APPLICABLE",
                skip_reason="Security review skipped for testing authority check",
                description="DEV-SEC Security Audit",
                affected_artifacts=["services/payment_service.py"],
            )
        ],
    )

    with pytest.raises(PolicyViolationError, match="not authorized by the development plan"):
        await sec_agent.review_security(
            tenant_id="tenant-beta",
            task_id="task-sec-001",
            candidate=clean_candidate,
            verification_dossier=passed_verification_dossier,
            plan=plan,
            task_grant=valid_grant,
        )


@pytest.mark.asyncio
async def test_read_only_invariance_fails_closed(
    sec_agent: SecurityReviewAgent,
    clean_candidate: CodeCandidateDeliverable,
    passed_verification_dossier: VerificationDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 7: Mutation or auto-fix requests fail closed with PolicyViolationError."""
    with pytest.raises(PolicyViolationError, match="strictly read-only"):
        await sec_agent.review_security(
            tenant_id="tenant-beta",
            task_id="task-sec-001",
            candidate=clean_candidate,
            verification_dossier=passed_verification_dossier,
            task_grant=valid_grant,
            context={"auto_fix": True},
        )


@pytest.mark.asyncio
async def test_sast_dangerous_eval_exec_detection(
    sec_agent: SecurityReviewAgent,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 8: Dynamic eval/exec yields CRITICAL hard-block finding and DENY verdict."""
    vuln_candidate = CodeCandidateDeliverable(
        candidate_id="cand-vuln-001",
        task_id="task-sec-001",
        workflow_id="wf-sec-001",
        attempt_id="att-1",
        component_name="PaymentService",
        source_code={
            "services/payment_service.py": (
                "def evaluate_code(user_input: str) -> None:\n"
                "    eval(user_input)\n"
            )
        },
        changed_files=["services/payment_service.py"],
        code_diffs=[],
        implementation_summary="Vulnerable candidate for testing.",
        sanity_check_result=CodeSanityCheckResult(compiler_passed=True, is_valid=True),
    )
    vuln_candidate.compute_candidate_hash()

    dossier = await sec_agent.review_security(
        tenant_id="tenant-beta",
        task_id="task-sec-001",
        candidate=vuln_candidate,
        task_grant=valid_grant,
    )

    assert dossier.verdict == SecurityVerdict.DENY
    assert dossier.hard_block_count >= 1
    assert any(
        f.rule_id == "SEC-SAST-001" and f.severity == SecuritySeverity.CRITICAL
        for f in dossier.findings
    )
    assert dossier.is_acceptable_for_release() is False


@pytest.mark.asyncio
async def test_secret_exposure_detection(
    sec_agent: SecurityReviewAgent,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 9: Hardcoded credentials / private keys yield hard-block finding and DENY."""
    secret_candidate = CodeCandidateDeliverable(
        candidate_id="cand-secret-001",
        task_id="task-sec-001",
        workflow_id="wf-sec-001",
        attempt_id="att-1",
        component_name="PaymentService",
        source_code={
            "services/config.py": (
                "AWS_ACCESS_KEY_ID = 'AKIA1234567890ABCDEF'\n"
                "API_SECRET_KEY = 'super_secret_token_12345'\n"
            )
        },
        changed_files=["services/config.py"],
        code_diffs=[],
        implementation_summary="Candidate with secrets.",
        sanity_check_result=CodeSanityCheckResult(compiler_passed=True, is_valid=True),
    )
    secret_candidate.compute_candidate_hash()

    dossier = await sec_agent.review_security(
        tenant_id="tenant-beta",
        task_id="task-sec-001",
        candidate=secret_candidate,
        task_grant=valid_grant,
    )

    assert dossier.verdict == SecurityVerdict.DENY
    assert dossier.hard_block_count >= 1
    assert any(f.category == SecurityCategory.SECRET for f in dossier.findings)


@pytest.mark.asyncio
async def test_sca_dependency_vulnerability_detection(
    sec_agent: SecurityReviewAgent,
    clean_candidate: CodeCandidateDeliverable,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 10: Vulnerable package yields SCA hard-block finding and DENY."""
    dossier = await sec_agent.review_security(
        tenant_id="tenant-beta",
        task_id="task-sec-001",
        candidate=clean_candidate,
        task_grant=valid_grant,
        context={"dependencies": {"cryptography": "40.0.0"}},
    )

    assert dossier.verdict == SecurityVerdict.DENY
    assert any(
        f.category == SecurityCategory.SCA and f.cve_id == "CVE-2023-38325"
        for f in dossier.findings
    )


@pytest.mark.asyncio
async def test_config_manifest_review(
    sec_agent: SecurityReviewAgent,
    clean_candidate: CodeCandidateDeliverable,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 11: Insecure manifest configs (DEBUG=True, privileged: true) yield DENY."""
    dossier = await sec_agent.review_security(
        tenant_id="tenant-beta",
        task_id="task-sec-001",
        candidate=clean_candidate,
        task_grant=valid_grant,
        context={
            "manifests": {
                "docker-compose.yml": (
                    "services:\n  app:\n    privileged: true\n"
                    "    environment:\n      - DEBUG=True\n"
                )
            }
        },
    )

    assert dossier.verdict == SecurityVerdict.DENY
    assert any(
        f.category == SecurityCategory.CONFIG and f.rule_id == "SEC-CFG-002"
        for f in dossier.findings
    )


@pytest.mark.asyncio
async def test_boundary_route_detection(
    sec_agent: SecurityReviewAgent,
    clean_candidate: CodeCandidateDeliverable,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 12: Unauthenticated routes yield permission boundary violation and DENY."""
    dossier = await sec_agent.review_security(
        tenant_id="tenant-beta",
        task_id="task-sec-001",
        candidate=clean_candidate,
        task_grant=valid_grant,
        context={
            "routes": [
                {"path": "/api/v1/admin/delete_all", "method": "DELETE", "authenticated": False}
            ]
        },
    )

    assert dossier.verdict == SecurityVerdict.DENY
    assert any(
        f.category == SecurityCategory.PERMISSION and f.rule_id == "SEC-PERM-001"
        for f in dossier.findings
    )


@pytest.mark.asyncio
async def test_ast_dangerous_pattern_detection(
    sec_agent: SecurityReviewAgent,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 13: Magic introspection attributes yield AST_PATTERN finding and DENY."""
    ast_candidate = CodeCandidateDeliverable(
        candidate_id="cand-ast-001",
        task_id="task-sec-001",
        workflow_id="wf-sec-001",
        attempt_id="att-1",
        component_name="PaymentService",
        source_code={
            "services/payment_service.py": (
                "def exploit() -> None:\n"
                "    x = ().__class__.__bases__[0].__subclasses__()\n"
            )
        },
        changed_files=["services/payment_service.py"],
        code_diffs=[],
        implementation_summary="AST candidate for testing.",
        sanity_check_result=CodeSanityCheckResult(compiler_passed=True, is_valid=True),
    )
    ast_candidate.compute_candidate_hash()

    dossier = await sec_agent.review_security(
        tenant_id="tenant-beta",
        task_id="task-sec-001",
        candidate=ast_candidate,
        task_grant=valid_grant,
    )

    assert dossier.verdict == SecurityVerdict.DENY
    assert any(
        f.category == SecurityCategory.AST_PATTERN and f.rule_id == "SEC-AST-001"
        for f in dossier.findings
    )


def test_security_dossier_deterministic_hashing() -> None:
    """Test 14: canonical_bytes and compute_dossier_hash produce identical hash for same content."""
    dossier1 = SecurityDossier(
        dossier_id="dossier-det-01",
        task_id="task-001",
        workflow_id="wf-001",
        candidate_hash="hash-1234",
        target_candidate_id="cand-001",
        component_name="PaymentService",
        verdict=SecurityVerdict.PASS,
        scanners_run=["scan_sast", "scan_secrets"],
        hard_block_count=0,
    )
    h1 = dossier1.compute_dossier_hash()

    dossier2 = SecurityDossier(
        dossier_id="dossier-det-01",
        task_id="task-001",
        workflow_id="wf-001",
        candidate_hash="hash-1234",
        target_candidate_id="cand-001",
        component_name="PaymentService",
        verdict=SecurityVerdict.PASS,
        scanners_run=["scan_secrets", "scan_sast"],  # reversed order
        hard_block_count=0,
    )
    h2 = dossier2.compute_dossier_hash()

    assert h1 == h2
    assert len(h1) == 64


@pytest.mark.asyncio
async def test_development_agent_execute_security_step(
    fake_sandbox: FakeSandboxClient,
    clean_candidate: CodeCandidateDeliverable,
    passed_verification_dossier: VerificationDossier,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Test 15: DevelopmentAgent integrates DEV-SEC and records provenance."""
    agent = DevelopmentAgent(sandbox_client=fake_sandbox)
    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repository=prov_repo)

    dossier = await agent.execute_security_step(
        grant=valid_grant,
        candidate=clean_candidate,
        verification_dossier=passed_verification_dossier,
        provenance_recorder=recorder,
    )

    assert isinstance(dossier, SecurityDossier)
    assert dossier.verdict == SecurityVerdict.PASS
    chain = prov_repo._chains.get("tenant-beta", [])
    assert len(chain) >= 1
    rec = chain[0]
    assert rec.agent == "DEV-SEC"
    assert rec.metadata["verdict"] == "PASS"


def test_micro_tools_security_operations_direct() -> None:
    """Test 16: Directly test DEV-SEC operations in execute_s_code."""
    # 1. scan_sast
    sast_res = execute_s_code(
        operation="scan_sast",
        source_code={"main.py": "import os\nos.system('rm -rf /')\n"},
    )
    assert sast_res["status"] == "DENIED"
    assert sast_res["verdict"] == "DENY"
    assert sast_res["hard_block_count"] >= 1

    # 2. scan_secrets
    sec_res = execute_s_code(
        operation="scan_secrets",
        source_code={"main.py": "KEY = '-----BEGIN RSA PRIVATE KEY-----\\nabc\\n'"},
    )
    assert sec_res["verdict"] == "DENY"

    # 3. scan_dependencies_sca
    sca_res = execute_s_code(
        operation="scan_dependencies_sca",
        dependencies={"jinja2": "3.0.0"},
    )
    assert sca_res["verdict"] == "DENY"

    # 4. review_manifest_configs
    cfg_res = execute_s_code(
        operation="review_manifest_configs",
        manifests={"app.env": "DEBUG=true\n"},
    )
    assert cfg_res["verdict"] == "DENY"

    # 5. check_authorization_boundaries
    bound_res = execute_s_code(
        operation="check_authorization_boundaries",
        routes=[{"path": "/unauth", "authenticated": False}],
    )
    assert bound_res["verdict"] == "DENY"

    # 6. analyze_ast_dangerous_patterns
    ast_res = execute_s_code(
        operation="analyze_ast_dangerous_patterns",
        source_code={"main.py": "def f(): return f.__globals__\n"},
    )
    assert ast_res["verdict"] == "DENY"

    # 7. read-only mutation rejected
    mut_res = execute_s_code(
        operation="scan_sast",
        mutation_attempted=True,
    )
    assert mut_res["status"] == "security_violation"
    assert mut_res["mutation_rejected"] is True
