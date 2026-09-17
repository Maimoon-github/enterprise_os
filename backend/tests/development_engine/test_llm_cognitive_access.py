"""Test LLM Cognitive Access (Think -> Ponder -> Reflect -> React) across Development Engine & Sub-Agents.

Validates:
1. DevelopmentAgent orchestration cognitive reasoning (reason_orchestration) with LLM and deterministic fallback.
2. DEV-PLAN (DevelopmentPlanningAgent) cognitive reflection and architectural insight generation.
3. DEV-CMS (CmsContractAgent) cognitive reasoning and backward-compatibility reflection.
4. DEV-UI (UiLayoutAgent) cognitive reasoning and design/accessibility reflection.
5. DEV-CODE (CodeImplementationAgent) cognitive reasoning and implementation reflection.
6. DEV-VERIFY (VerificationAgent) cognitive diagnosis of verification checks without mutating source.
7. DEV-SEC (SecurityReviewAgent) cognitive threat modeling and remediation guidance with hard machine gate.
8. DEV-REL (ReleaseOpsAgent) cognitive operational risk and rollback reflection with strict packaging bounds.
9. End-to-end LLM cognitive wiring from DevelopmentAgent down to all specialist sub-agents.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from typing import Any
import pytest

from app.agents.development_engine.development import DevelopmentAgent
from app.agents.development_engine.subagents.cms_contract import CmsContractAgent
from app.agents.development_engine.subagents.implementation import CodeImplementationAgent
from app.agents.development_engine.subagents.planning import DevelopmentPlanningAgent
from app.agents.development_engine.subagents.release_ops import ReleaseOpsAgent
from app.agents.development_engine.subagents.security_review import SecurityReviewAgent
from app.agents.development_engine.subagents.ui_layout import UiLayoutAgent
from app.agents.development_engine.subagents.verification import VerificationAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.development.development_plan import DevelopmentPlan, DevelopmentPlanStep
from app.schemas.development.development_result import (
    CodeCandidateDeliverable,
    CodeSanityCheckResult,
    DevelopmentTaskGrant,
    SecurityDossier,
    SecurityVerdict,
    VerificationDossier,
    VerificationVerdict,
)
from app.schemas.governance import TenantScope, WorkerRole
from tests.conftest import FakeSandboxClient


class UniversalFakeLlmClient:
    """Mock LLM client supporting both generate and complete with customized responses."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.call_count = 0
        self.invocations: list[dict[str, Any]] = []
        self.responses = responses or {}

    async def generate(
        self,
        prompt: str | None = None,
        *,
        system: str | None = None,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        self.call_count += 1
        eff_user = user_prompt or prompt or ""
        eff_sys = system_prompt or system or ""
        self.invocations.append({"user": eff_user, "system": eff_sys, "kwargs": kwargs})

        # Match specific response if available
        for key, resp in self.responses.items():
            if key.lower() in eff_user.lower() or key.lower() in eff_sys.lower():
                return json.dumps(resp) if isinstance(resp, dict) else str(resp)

        # Default structured cognitive response
        return json.dumps({
            "thought_process": "Cognitive LLM reasoned and pondered software architecture.",
            "diagnostic_thought": "Analyzed test failures and formulated diagnostic insights.",
            "threat_thought": "Pondered threat landscape and evaluated AST risks.",
            "release_thought": "Reflected on release bundle readiness and rollback strategy.",
            "orchestration_thought": "Pondered development lifecycle status and dependencies.",
            "lifecycle_reflection": "Lifecycle reflection: progress is stable across subagents.",
            "recommended_next_action": "Proceed to next development phase.",
            "cognitive_confidence": 0.95,
            "failure_root_causes": ["Simulated failure cause identified by cognitive loop."],
            "remediation_directives": ["Remediate check failure in target module."],
            "remediation_guidance": ["Ensure all parameters are sanitized before execution."],
            "operational_risks": ["Verify memory consumption during high concurrency."],
            "rollback_recommendations": ["Revert to prior stable release snapshot if canary fails."],
            "release_readiness": "APPROVED",
        })

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        return await self.generate(prompt=prompt, system=system)


@pytest.fixture
def fake_sandbox() -> FakeSandboxClient:
    return FakeSandboxClient()


@pytest.fixture
def task_grant() -> DevelopmentTaskGrant:
    return DevelopmentTaskGrant(
        task_id="task-llm-cog-001",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-acme"),
        brand_id="brand-core",
        objective="Implement and verify secure cognitive development workflow",
        component_name="NavbarComponent",
        target_files=[
            "schemas/navigation.json",
            "templates/navbar.html",
            "components/navbar.py",
        ],
        token_budget=8000,
        expires_at=datetime.now(UTC) + timedelta(minutes=45),
    )


@pytest.mark.asyncio
async def test_development_agent_orchestration_cognitive_reasoning(
    fake_sandbox: FakeSandboxClient,
) -> None:
    """Test DevelopmentAgent orchestration-level cognitive loop."""
    llm = UniversalFakeLlmClient()
    agent = DevelopmentAgent(fake_sandbox, llm_client=llm)

    # 1. With LLM configured
    res = await agent.reason_orchestration(
        objective="Deploy CMS v2",
        active_subagent="DEV-VERIFY",
        task_id="task-123",
        current_state={"phase": "VERIFICATION_RUNNING"},
        feedback="Requires strict lint compliance",
    )
    assert llm.call_count == 1
    assert "orchestration_thought" in res
    assert "lifecycle_reflection" in res
    assert "recommended_next_action" in res
    assert res["cognitive_confidence"] == 0.95

    # 2. Deterministic fallback when LLM is None
    agent_no_llm = DevelopmentAgent(fake_sandbox, llm_client=None)
    fallback_res = await agent_no_llm.reason_orchestration(
        objective="Deploy CMS v2",
        active_subagent="DEV-VERIFY",
        task_id="task-123",
    )
    assert "orchestration_thought" in fallback_res
    assert "Proceed with DEV-VERIFY execution." in fallback_res["recommended_next_action"]


@pytest.mark.asyncio
async def test_dev_plan_cognitive_reasoning(
    fake_sandbox: FakeSandboxClient, task_grant: DevelopmentTaskGrant
) -> None:
    """Test DEV-PLAN cognitive loop for architectural thinking and reflection."""
    custom_plan_resp = {
        "thought_process": "Pondered microservice decoupling and zero-downtime migrations.",
        "architectural_insights": [
            "Decompose into modular CMS contract and responsive UI layout.",
            "Maintain backward compatibility with v1 API endpoints.",
        ],
        "risk_assessment": "Low risk additive change.",
        "reflection_notes": "Addressed reviewer comments regarding schema validation.",
    }
    llm = UniversalFakeLlmClient(responses={"DEV-PLAN": custom_plan_resp})
    planning_agent = DevelopmentPlanningAgent(fake_sandbox, llm_client=llm)

    plan = await planning_agent.create_plan(
        grant=task_grant,
        reviewer_feedback="Ensure backward compatibility.",
        is_release_producing=True,
    )

    assert plan.plan_hash is not None
    assert llm.call_count >= 1
    assert "cognitive_reasoning" in plan.discovered_facts
    cog = plan.discovered_facts["cognitive_reasoning"]
    assert cog["thought_process"] == "Pondered microservice decoupling and zero-downtime migrations."
    assert len(cog["architectural_insights"]) == 2


@pytest.mark.asyncio
async def test_dev_verify_cognitive_reasoning(
    fake_sandbox: FakeSandboxClient, task_grant: DevelopmentTaskGrant
) -> None:
    """Test DEV-VERIFY cognitive reflection on test/lint diagnostics."""
    verify_llm = UniversalFakeLlmClient(
        responses={
            "DEV-VERIFY": {
                "diagnostic_thought": "Analyzed syntax error in handler.py at line 42.",
                "failure_root_causes": ["Missing closing parenthesis in database query."],
                "remediation_directives": ["Direct DEV-CODE to patch syntax in handler.py."],
            }
        }
    )
    verify_agent = VerificationAgent(fake_sandbox, llm_client=verify_llm)

    candidate = CodeCandidateDeliverable(
        candidate_id="cand-001",
        task_id=task_grant.task_id,
        workflow_id="wf-001",
        component_name="BlogService",
        source_code={"main.py": "def run():\n    return 'ok'\n"},
        sanity_check_result=CodeSanityCheckResult(is_valid=True, syntax_valid=True, compiler_passed=True),
    )
    candidate.compute_candidate_hash()

    # Pass context simulating a lint failure to trigger diagnostic cognitive reflection
    dossier = await verify_agent.execute_verification_task(
        grant=task_grant,
        candidate=candidate,
        context={"simulate_lint_errors": ["services/payment_service.py:1: [F401] 'os' imported but unused"]},
    )

    assert dossier.verdict == VerificationVerdict.FAIL
    assert verify_llm.call_count >= 1
    assert "llm_reasoning" in dossier.provenance
    cog = dossier.provenance["llm_reasoning"]
    assert "syntax error" in cog["diagnostic_thought"].lower()
    assert len(cog["remediation_directives"]) >= 1


@pytest.mark.asyncio
async def test_dev_sec_cognitive_reasoning(
    fake_sandbox: FakeSandboxClient, task_grant: DevelopmentTaskGrant
) -> None:
    """Test DEV-SEC cognitive reflection on threat modeling and remediation."""
    sec_llm = UniversalFakeLlmClient(
        responses={
            "DEV-SEC": {
                "threat_thought": "Pondered threat exposure for unauthenticated route and secret leak.",
                "risk_analysis": ["Hard block on exposed AWS credentials in config.py."],
                "remediation_guidance": ["Move AWS credentials to environment variables and vault."],
            }
        }
    )
    sec_agent = SecurityReviewAgent(fake_sandbox, llm_client=sec_llm)

    candidate = CodeCandidateDeliverable(
        candidate_id="cand-sec-001",
        task_id=task_grant.task_id,
        workflow_id="wf-sec-001",
        component_name="AuthService",
        source_code={"config.py": "AWS_SECRET_KEY = 'AKIA1234567890123456'\n"},
        sanity_check_result=CodeSanityCheckResult(is_valid=True, syntax_valid=True, compiler_passed=True),
    )
    candidate.compute_candidate_hash()

    # Simulate passing verification dossier prerequisite
    ver_dossier = VerificationDossier(
        dossier_id="ver-001",
        task_id=task_grant.task_id,
        workflow_id="wf-sec-001",
        candidate_hash=candidate.candidate_hash,
        target_candidate_id=candidate.candidate_id,
        component_name="AuthService",
        verdict=VerificationVerdict.PASS,
    )

    dossier = await sec_agent.execute_security_task(
        grant=task_grant,
        candidate=candidate,
        verification_dossier=ver_dossier,
    )

    assert dossier.verdict == SecurityVerdict.DENY
    assert sec_llm.call_count >= 1
    assert "llm_reasoning" in dossier.provenance
    cog = dossier.provenance["llm_reasoning"]
    assert "threat exposure" in cog["threat_thought"].lower()
    assert len(cog["remediation_guidance"]) >= 1


@pytest.mark.asyncio
async def test_dev_rel_cognitive_reasoning(
    fake_sandbox: FakeSandboxClient, task_grant: DevelopmentTaskGrant
) -> None:
    """Test DEV-REL cognitive reflection on packaging, SBOM, and rollback."""
    rel_llm = UniversalFakeLlmClient(
        responses={
            "DEV-REL": {
                "release_thought": "Reflected on multi-architecture container artifacts and SBOM tree.",
                "operational_risks": ["Monitor schema lock duration during initial table migration."],
                "rollback_recommendations": ["Perform zero-downtime drain of pod replica sets."],
                "release_readiness": "READY_FOR_STAGING",
            }
        }
    )
    rel_agent = ReleaseOpsAgent(fake_sandbox, llm_client=rel_llm)

    candidate = CodeCandidateDeliverable(
        candidate_id="cand-rel-001",
        task_id=task_grant.task_id,
        workflow_id="wf-rel-001",
        component_name="ReleaseTarget",
        source_code={"main.py": "print('hello release')\n"},
        sanity_check_result=CodeSanityCheckResult(is_valid=True, syntax_valid=True, compiler_passed=True),
    )
    candidate.compute_candidate_hash()

    clean_sec_dossier = SecurityDossier(
        dossier_id="sec-clean-001",
        task_id=task_grant.task_id,
        workflow_id="wf-rel-001",
        candidate_hash=candidate.candidate_hash,
        target_candidate_id=candidate.candidate_id,
        component_name="ReleaseTarget",
        verdict=SecurityVerdict.PASS,
        hard_block_count=0,
    )

    deliverable = await rel_agent.execute_release_task(
        grant=task_grant,
        candidate=candidate,
        security_dossier=clean_sec_dossier,
        hitl_approved=True,
    )

    assert deliverable.release_hash is not None
    assert rel_llm.call_count >= 1
    assert "llm_reasoning" in deliverable.provenance
    cog = deliverable.provenance["llm_reasoning"]
    assert "container artifacts" in cog["release_thought"].lower()
    assert "READY_FOR_STAGING" in cog["release_readiness"]


@pytest.mark.asyncio
async def test_dev_cms_cognitive_reasoning(
    fake_sandbox: FakeSandboxClient, task_grant: DevelopmentTaskGrant
) -> None:
    """Test DEV-CMS cognitive reasoning and backward compatibility reflection."""
    cms_llm = UniversalFakeLlmClient(
        responses={
            "DEV-CMS": {
                "rationale": "Add author_bio to BlogPost model.",
                "breaking_analysis": "Additive change: backward-compatible.",
                "migration_strategy": "Direct migration.",
                "constraints_considered": ["field naming convention"],
                "feedback_adjustments": [],
            }
        }
    )
    cms_agent = CmsContractAgent(fake_sandbox, llm_client=cms_llm)
    res = await cms_agent._reason_with_llm(
        objective="Add author bio to BlogPost",
        context={"model_name": "BlogPost"},
        base_schema={
            "model_name": "BlogPost",
            "fields": [
                {"name": "title", "type": "string"},
                {"name": "content", "type": "string"},
            ],
        },
        reviewer_feedback="Consider indexing author_bio",
    )
    assert cms_llm.call_count >= 1
    assert "llm_reasoning" in res
    assert "rationale" in res["llm_reasoning"]
    assert "breaking_analysis" in res["llm_reasoning"]


@pytest.mark.asyncio
async def test_dev_ui_cognitive_reasoning(
    fake_sandbox: FakeSandboxClient, task_grant: DevelopmentTaskGrant
) -> None:
    """Test DEV-UI cognitive reasoning and layout/accessibility reflection."""
    ui_llm = UniversalFakeLlmClient(
        responses={
            "DEV-UI": {
                "design_rationale": "Responsive flex layout with WCAG AA compliance.",
                "component_structure": "Navbar containing BrandLogo and NavLinks.",
                "accessibility_considerations": ["Aria attributes for mobile drawer."],
                "responsive_strategy": "Mobile-first CSS grid breakpoints.",
            }
        }
    )
    ui_agent = UiLayoutAgent(fake_sandbox, llm_client=ui_llm)
    res = await ui_agent._reason_with_llm(
        objective="Create responsive navbar",
        context={},
        component_name="Navbar",
        cms_contract={"model_name": "BlogPost"},
        reviewer_feedback="Ensure high contrast theme toggle",
    )
    assert ui_llm.call_count >= 1
    assert "design_rationale" in res
    assert "accessibility_considerations" in res


@pytest.mark.asyncio
async def test_dev_code_cognitive_reasoning(
    fake_sandbox: FakeSandboxClient, task_grant: DevelopmentTaskGrant
) -> None:
    """Test DEV-CODE cognitive reasoning and implementation reflection."""
    code_llm = UniversalFakeLlmClient(
        responses={
            "DEV-CODE": {
                "implementation_thought": "Authoring service handlers with robust error wrapping.",
                "refactoring_rationale": "Extract business logic into pure function.",
                "error_handling_strategy": "Custom DomainException with tenant correlation ID.",
                "syntax_validation_notes": "AST tree verified for async/await correctness.",
            }
        }
    )
    code_agent = CodeImplementationAgent(fake_sandbox, llm_client=code_llm)
    res = await code_agent._reason_with_llm(
        objective="Implement payment processing logic",
        context={},
        component_name="PaymentHandler",
        target_files=["services/payment.py"],
        reviewer_feedback="Handle gateway timeout",
    )
    assert code_llm.call_count >= 1
    assert "implementation_thought" in res
    assert "error_handling_strategy" in res


@pytest.mark.asyncio
async def test_development_agent_end_to_end_subagent_llm_propagation(
    fake_sandbox: FakeSandboxClient,
) -> None:
    """Verify that instantiating DevelopmentAgent with llm_client equips all sub-agents with LLM cognitive access."""
    llm = UniversalFakeLlmClient()
    dev_engine = DevelopmentAgent(fake_sandbox, llm_client=llm)

    assert dev_engine.llm_client is llm
    assert dev_engine.planning_agent._llm_client is llm
    assert dev_engine.cms_agent._llm_client is llm
    assert dev_engine.ui_agent._llm_client is llm
    assert dev_engine.code_agent._llm_client is llm
    assert dev_engine.verify_agent._llm_client is llm
    assert dev_engine.security_agent._llm_client is llm
    assert dev_engine.release_agent._llm_client is llm
