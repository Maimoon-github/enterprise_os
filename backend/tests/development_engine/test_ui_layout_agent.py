"""Comprehensive unit and integration tests for Task DE-08: DEV-UI.

Validates:
1. DEV-UI enforces approved plan authority (fails closed if DEV-UI was skipped).
2. UI layout and component generation with responsive rules, templates, and design tokens.
3. Scope boundary enforcement (fails closed if proposed mutations target unauthorized artifacts).
4. Tenant isolation breach rejection.
5. Handoff from predecessor CMS contracts (DE-07) and contract compatibility checks.
6. Localhost multi-viewport render simulation & render evidence capture inside sandbox.
7. Automated WCAG 2.2 A/AA accessibility scanning and evidence generation (with disclaimer).
8. LLM reasoning engine integration and deterministic offline fallback.
9. Rejection and revision continuity (att-1 -> att-2) preserving att-1 immutability.
10. Deterministic candidate hash sealing and canonical byte representation.
11. Integration with DevelopmentAgent.execute_ui_step and ProvenanceRecorder.
12. Direct sandbox micro_tools execution for all UI operations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from typing import Any
import pytest

from app.agents.development_engine.development import DevelopmentAgent
from app.agents.development_engine.subagents.ui_layout import UiLayoutAgent
from app.core.exceptions import PolicyViolationError
from app.integrations.sandbox.micro_tools import execute_s_code
from app.schemas.agent_contracts import TaskGrant
from app.schemas.cms import (
    CmsCandidateDeliverable,
    CmsChangeClassification,
    CmsCompatibilityReport,
    CmsContentModelSchema,
    CmsFieldDefinition,
    CmsFieldType,
    CmsValidationEvidence,
)
from app.schemas.development import (
    DevelopmentPlan,
    DevelopmentPlanStep,
    DevelopmentTaskGrant,
    UiAccessibilityReport,
    UiCandidateDeliverable,
    UiRenderEvidence,
    UiValidationEvidence,
    UiViewportRender,
    WcagFinding,
    WcagSeverity,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository, FakeSandboxClient


class FakeLlmClient:
    """Mock LLM client returning realistic JSON responses for UI layout planning."""

    def __init__(self, response_dict: dict[str, Any] | None = None) -> None:
        self.call_count = 0
        self.last_prompt = ""
        self.response_dict = response_dict or {
            "template_markup": (
                "<section class=\"blog-card-section\" aria-label=\"Blog Card\">\n"
                "  <header><h1>{{ title }}</h1><p>{{ subtitle }}</p></header>\n"
                "  <main><p>{{ author_bio }}</p></main>\n"
                "  <button type=\"button\" aria-label=\"Read More\">Read More</button>\n"
                "</section>"
            ),
            "css_styles": ".blog-card-section { display: flex; flex-direction: column; }",
            "component_code": "class BlogCard:\n    def render(self, context=None):\n        return '<div>BlogCard</div>'\n",
            "design_tokens": {"color_primary": "#2563EB", "font_family": "Inter"},
            "props_schema": {
                "title": {"type": "string", "required": True},
                "subtitle": {"type": "string", "required": False},
                "author_bio": {"type": "string", "required": False},
            },
            "rationale": "Constructed accessible, responsive blog card component.",
            "responsive_notes": "Implemented mobile-first flexbox with responsive tablet and desktop grid.",
        }

    async def generate(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        self.call_count += 1
        self.last_prompt = user_prompt
        return self.response_dict


@pytest.fixture
def fake_sandbox() -> FakeSandboxClient:
    return FakeSandboxClient()


@pytest.fixture
def ui_agent(fake_sandbox: FakeSandboxClient) -> UiLayoutAgent:
    return UiLayoutAgent(sandbox_client=fake_sandbox)


@pytest.fixture
def valid_grant() -> DevelopmentTaskGrant:
    return DevelopmentTaskGrant(
        task_id="task-ui-test-01",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        brand_id="brand-core",
        objective="Implement responsive BlogCard UI component",
        component_name="BlogCard",
        component_type="component",
        target_files=["components/blog-card.py", "templates/blog-card.html", "styles/blog-card.css"],
        allowed_operations=["validate_template", "format_ui_code", "render_ui_view", "compile_component", "scan_accessibility_wcag"],
        sandbox_capabilities=[SandboxCapability.CODE.value],
        token_budget=8000,
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )


@pytest.fixture
def valid_plan(valid_grant: DevelopmentTaskGrant) -> DevelopmentPlan:
    return DevelopmentPlan(
        plan_id="plan-ui-01",
        task_id=valid_grant.task_id,
        workflow_id="wf-test-ui-01",
        objective="Implement responsive BlogCard UI component",
        affected_files=["components/blog-card.py", "templates/blog-card.html", "styles/blog-card.css"],
        steps=[
            DevelopmentPlanStep(
                step_id="step-cms-01",
                subagent_id="DEV-CMS",
                status="REQUIRED",
                description="Evolve blog post schema to include author_bio",
            ),
            DevelopmentPlanStep(
                step_id="step-ui-01",
                subagent_id="DEV-UI",
                status="REQUIRED",
                description="Implement BlogCard UI component",
                affected_artifacts=["components/blog-card.py", "templates/blog-card.html", "styles/blog-card.css"],
            ),
        ],
    )


# ===========================================================================
# 1. UI Layout & Component Generation Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_ui_layout_generation_success(
    ui_agent: UiLayoutAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-UI generates a sealed candidate deliverable with responsive templates, styles, and diffs."""
    context = {
        "tenant_id": "tenant-alpha",
        "component_name": "BlogCard",
        "current_schema": {
            "model_name": "blog_post",
            "fields": [
                {"name": "title", "field_type": "string", "required": True},
                {"name": "author_bio", "field_type": "string", "required": False},
            ],
        },
    }

    candidate = await ui_agent.execute_ui_task(
        grant=valid_grant,
        plan=valid_plan,
        context=context,
    )

    assert isinstance(candidate, UiCandidateDeliverable)
    assert candidate.task_id == valid_grant.task_id
    assert candidate.component_name == "BlogCard"
    assert candidate.attempt_id == "att-1"
    assert len(candidate.templates) >= 1
    assert len(candidate.code_diffs) >= 1
    assert candidate.candidate_hash is not None and len(candidate.candidate_hash) == 64

    # Template checks
    tmpl = candidate.primary_template
    assert "BlogCard" in tmpl.name
    assert tmpl.template_markup is not None and len(tmpl.template_markup) > 0
    assert len(tmpl.responsive_breakpoints) == 3

    # Multi-viewport render evidence checks
    render = candidate.render_evidence
    assert render.simulated_in_sandbox is True
    assert render.zero_external_egress_verified is True
    assert len(render.viewports) == 3
    assert render.all_viewports_rendered is True

    # WCAG 2.2 A/AA accessibility checks
    a11y = candidate.accessibility_report
    assert a11y.target_standard == "WCAG 2.2 A/AA"
    assert a11y.rules_evaluated >= 5
    assert a11y.compliance_score >= 90.0
    assert a11y.is_accessible is True
    assert "Automated scan provides evidence" in a11y.disclaimer


# ===========================================================================
# 2. Plan Authority Enforcement Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_plan_authority_enforced_fails_if_skipped(
    ui_agent: UiLayoutAgent,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Fails closed if the approved DevelopmentPlan specifies DEV-UI as SKIPPED_NOT_APPLICABLE."""
    skipped_plan = DevelopmentPlan(
        plan_id="plan-skip-ui",
        task_id=valid_grant.task_id,
        workflow_id="wf-test-01",
        objective="Update backend service without UI changes",
        steps=[
            DevelopmentPlanStep(
                step_id="step-ui",
                subagent_id="DEV-UI",
                status="SKIPPED_NOT_APPLICABLE",
                skip_reason="Task is headless backend API adjustment with no frontend surface.",
            ),
        ],
    )

    with pytest.raises(PolicyViolationError) as exc_info:
        await ui_agent.execute_ui_task(
            grant=valid_grant,
            plan=skipped_plan,
            context={"tenant_id": "tenant-alpha"},
        )
    assert "SKIPPED_NOT_APPLICABLE" in str(exc_info.value)


@pytest.mark.asyncio
async def test_plan_authority_passes_when_required(
    ui_agent: UiLayoutAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Succeeds when approved DevelopmentPlan specifies DEV-UI as REQUIRED."""
    candidate = await ui_agent.execute_ui_task(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )
    assert candidate.candidate_id is not None
    assert candidate.component_name == "BlogCard"


# ===========================================================================
# 3. Scope Boundary & Tenant Isolation Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_scope_boundary_violation_rejected(
    ui_agent: UiLayoutAgent,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Fails closed if the proposed UI artifacts are outside plan-authorized artifacts."""
    restricted_plan = DevelopmentPlan(
        plan_id="plan-restricted",
        task_id=valid_grant.task_id,
        workflow_id="wf-test-01",
        objective="Create unauthorized widget",
        affected_files=["components/navbar.py"],  # blog-card is NOT authorized
        steps=[
            DevelopmentPlanStep(
                step_id="step-ui",
                subagent_id="DEV-UI",
                status="REQUIRED",
                description="Update navbar only",
                affected_artifacts=["components/navbar.py"],
            ),
        ],
    )

    with pytest.raises(PolicyViolationError) as exc_info:
        await ui_agent.execute_ui_task(
            grant=valid_grant,
            plan=restricted_plan,
            context={"tenant_id": "tenant-alpha", "component_name": "BlogCard"},
        )
    assert "Scope boundary violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tenant_isolation_breach_rejected(
    ui_agent: UiLayoutAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Rejects execution if context tenant does not match grant tenant."""
    with pytest.raises(PolicyViolationError) as exc_info:
        await ui_agent.execute_ui_task(
            grant=valid_grant,
            plan=valid_plan,
            context={"tenant_id": "tenant-bravo"},
        )
    assert "Tenant isolation breach" in str(exc_info.value)


# ===========================================================================
# 4. Handoff from Predecessor CMS Contracts (DE-07)
# ===========================================================================

@pytest.mark.asyncio
async def test_cms_contract_handoff_and_compatibility(
    ui_agent: UiLayoutAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Consumes predecessor CmsCandidateDeliverable and reflects CMS fields in UI template."""
    cms_candidate = CmsCandidateDeliverable(
        candidate_id="cand-cms-001",
        task_id=valid_grant.task_id,
        workflow_id=valid_plan.workflow_id,
        schemas=[
            CmsContentModelSchema(
                model_name="blog_post",
                fields=[
                    CmsFieldDefinition(name="title", field_type=CmsFieldType.STRING, required=True),
                    CmsFieldDefinition(name="author_bio", field_type=CmsFieldType.TEXT, required=False),
                ],
            )
        ],
        compatibility_report=CmsCompatibilityReport(is_compatible=True, classification=CmsChangeClassification.ADDITIVE),
        validation_evidence=CmsValidationEvidence(ast_valid=True, simulated_success=True),
        candidate_hash="hash-cms-001",
    )

    candidate = await ui_agent.execute_ui_task(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha", "cms_candidate": cms_candidate},
    )

    assert candidate.cms_contract_hash == "hash-cms-001"
    assert candidate.validation_evidence.cms_contract_compatible is True
    # Verify author_bio was bound into the props or template
    assert "author_bio" in candidate.primary_template.props_schema


# ===========================================================================
# 5. Localhost Rendering & WCAG 2.2 A/AA Accessibility Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_render_evidence_and_accessibility_disclaimer(
    ui_agent: UiLayoutAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Verifies multi-viewport rendering, screenshot hashes, and automated WCAG 2.2 A/AA findings."""
    candidate = await ui_agent.execute_ui_task(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )

    render = candidate.render_evidence
    assert len(render.viewports) == 3
    viewport_names = [v.viewport_name for v in render.viewports]
    assert "mobile" in viewport_names
    assert "tablet" in viewport_names
    assert "desktop" in viewport_names

    # Check DOM snapshot hashes are generated
    for vp in render.viewports:
        assert vp.render_status == "SUCCESS"
        assert len(vp.dom_snapshot_hash) == 64

    # Check accessibility findings
    a11y = candidate.accessibility_report
    assert a11y.contrast_ratio_verified is True
    assert a11y.disclaimer != ""
    assert "Automated scan provides evidence" in a11y.disclaimer


@pytest.mark.asyncio
async def test_accessibility_contrast_failure_flagged(
    ui_agent: UiLayoutAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Flags WCAG 1.4.3 contrast failure when contrast ratio check fails."""
    candidate = await ui_agent.execute_ui_task(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha", "simulate_contrast_failure": True},
    )

    a11y = candidate.accessibility_report
    assert a11y.contrast_ratio_verified is False
    contrast_findings = [f for f in a11y.findings if "CONTRAST" in f.rule_id]
    assert len(contrast_findings) == 1
    assert contrast_findings[0].is_passed is False
    assert contrast_findings[0].severity == WcagSeverity.SERIOUS


# ===========================================================================
# 6. Cognitive LLM Reasoning & Fallback Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_llm_reasoning_integration(
    fake_sandbox: FakeSandboxClient,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-UI utilizes LLM reasoning engine when LLM client is configured."""
    fake_llm = FakeLlmClient()
    agent = UiLayoutAgent(sandbox_client=fake_sandbox, llm_client=fake_llm)

    candidate = await agent.execute_ui_task(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )

    assert fake_llm.call_count >= 1
    assert "BlogCard" in fake_llm.last_prompt
    assert candidate.primary_template.template_markup is not None


@pytest.mark.asyncio
async def test_deterministic_fallback_without_llm(
    fake_sandbox: FakeSandboxClient,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DEV-UI falls back seamlessly to deterministic rule-based planning when LLM is unavailable."""
    agent = UiLayoutAgent(sandbox_client=fake_sandbox, llm_client=None)

    candidate = await agent.execute_ui_task(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )

    assert candidate.candidate_hash is not None
    assert candidate.primary_template.template_markup is not None
    assert candidate.validation_evidence.template_syntax_valid is True


# ===========================================================================
# 7. Rejection & Revision Continuity Tests (DE-04 HITL Handshake)
# ===========================================================================

@pytest.mark.asyncio
async def test_rejection_and_revision_attempt_handling(
    ui_agent: UiLayoutAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """On HITL rejection, produces att-2 addressing reviewer feedback while preserving att-1 immutability."""
    # Attempt 1: Initial creation
    att1_candidate = await ui_agent.execute_ui_task(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
        attempt_id="att-1",
    )
    att1_hash = att1_candidate.candidate_hash

    # Human reviewer rejects with feedback
    reviewer_notes = "Increase accessible landmark labeling on main container."

    # Attempt 2: Revision incorporating feedback
    att2_candidate = await ui_agent.execute_ui_task(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha", "rejection_feedback": reviewer_notes},
        attempt_id="att-2",
        previous_candidate=att1_candidate,
        reviewer_feedback=reviewer_notes,
    )

    # Immutability verification: att-1 remains unchanged
    assert att1_candidate.attempt_id == "att-1"
    assert att1_candidate.candidate_hash == att1_hash

    # att-2 has new attempt ID and captures feedback
    assert att2_candidate.attempt_id == "att-2"
    assert att2_candidate.rejection_feedback == reviewer_notes
    assert att2_candidate.candidate_hash != att1_hash


# ===========================================================================
# 8. Deterministic Candidate Sealing & DevelopmentAgent Integration
# ===========================================================================

@pytest.mark.asyncio
async def test_deterministic_candidate_sealing(
    ui_agent: UiLayoutAgent,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """Candidate hash is strictly deterministic based on canonical serialized bytes."""
    cand1 = await ui_agent.execute_ui_task(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )
    cand2 = await ui_agent.execute_ui_task(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
    )

    # Same content -> identical canonical bytes and candidate hash
    assert cand1.canonical_bytes() == cand2.canonical_bytes()
    assert cand1.candidate_hash == cand2.candidate_hash

    # Mapping to standard DevelopmentDeliverable
    dev_deliverable = cand1.to_development_deliverable(tenant_id="tenant-alpha")
    assert dev_deliverable.deliverable_id == f"dev-ui-{cand1.candidate_id}"
    assert len(dev_deliverable.ui_templates) == len(cand1.templates)
    assert dev_deliverable.provenance["candidate_hash"] == cand1.candidate_hash


@pytest.mark.asyncio
async def test_development_agent_execute_ui_step_with_provenance(
    fake_sandbox: FakeSandboxClient,
    valid_grant: DevelopmentTaskGrant,
    valid_plan: DevelopmentPlan,
) -> None:
    """DevelopmentAgent orchestrates execute_ui_step and logs tamper-evident DE-05 provenance."""
    dev_agent = DevelopmentAgent(sandbox_client=fake_sandbox)
    fake_prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repository=fake_prov_repo)

    candidate, cand_hash = await dev_agent.execute_ui_step(
        grant=valid_grant,
        plan=valid_plan,
        context={"tenant_id": "tenant-alpha"},
        provenance_recorder=recorder,
    )

    assert candidate.candidate_hash == cand_hash
    # Verify provenance was immutably recorded
    tenant_id = valid_grant.tenant_scope.tenant_id
    events = fake_prov_repo._chains.get(tenant_id, [])
    assert len(events) >= 1
    ui_event = [e for e in events if e.agent == "DEV-UI"][0]
    assert ui_event.tenant_id == tenant_id
    assert ui_event.metadata["candidate_hash"] == cand_hash
    assert ui_event.metadata["component_name"] == "BlogCard"


# ===========================================================================
# 9. Direct Sandbox Micro-Tools Execution Tests
# ===========================================================================

def test_sandbox_micro_tools_ui_operations() -> None:
    """Directly verifies sandbox micro-tools execution for all UI operations in S_CODE."""
    markup = (
        "<section class=\"profile-card\" aria-label=\"User Profile\">\n"
        "  <header><h1>{{ name }}</h1></header>\n"
        "  <main><p>{{ bio }}</p></main>\n"
        "  <button type=\"button\" aria-label=\"Follow User\">Follow</button>\n"
        "</section>"
    )
    styles = ".profile-card { width: 100%; }"

    # 1. validate_template
    val = execute_s_code("validate_template", template_markup=markup, css_styles=styles)
    assert val.get("is_valid") is True
    assert val.get("syntax_valid") is True

    # 2. format_ui_code
    fmt = execute_s_code("format_ui_code", template_markup=markup, css_styles=styles)
    assert fmt.get("is_formatted") is True
    assert len(fmt.get("formatted_markup", "")) > 0

    # 3. compile_component
    comp = execute_s_code("compile_component", code="class ProfileCard:\n    pass\n", component_name="ProfileCard")
    assert comp.get("ast_valid") is True
    assert comp.get("class_count") == 1

    # 4. render_ui_view
    rnd = execute_s_code("render_ui_view", template_markup=markup, css_styles=styles, component_name="ProfileCard")
    assert rnd.get("all_rendered") is True
    assert len(rnd.get("viewports", [])) == 3
    assert rnd.get("visual_snapshot_hash") is not None

    # 5. capture_render_evidence
    ev = execute_s_code("capture_render_evidence", render_data=rnd, component_name="ProfileCard")
    assert ev.get("simulated_in_sandbox") is True
    assert ev.get("zero_external_egress_verified") is True

    # 6. scan_accessibility_wcag
    wcag = execute_s_code("scan_accessibility_wcag", template_markup=markup, css_styles=styles)
    assert wcag.get("compliance_score") == 100.0
    assert wcag.get("contrast_ratio_verified") is True
    assert "Automated scan provides evidence" in wcag.get("disclaimer", "")
