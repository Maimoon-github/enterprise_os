"""Integration tests for domain specialist agents, RBAC guardrails, and adversarial veto."""

import pytest
from src.agents.analyst_agent import AnalystAgent
from src.agents.audience_agent import AudienceAgent
from src.agents.brand_agent import BrandAgent
from src.agents.growth_agent import GrowthAgent
from src.agents.seo_content_agent import SEOContentAgent
from src.agents.validator_agent import ValidatorAgent
from src.orchestrator.manager import StrategyOrchestrator
from src.schemas.initiative import ApprovalStatus, PriorityLevel, StrategicInitiative, SuccessMetric
from src.schemas.state import OperationalMode


def test_agent_rbac_whitelist_enforcement():
    agent = AudienceAgent()
    # Attempting to register an un-whitelisted tool must trigger PermissionError
    with pytest.raises(PermissionError) as exc_info:
        agent.register_tool("unauthorized_shell_exec", lambda: "evil")
    assert "Security Violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_analyst_agent_execution():
    agent = AnalystAgent()
    slice_data = {"website_url": "https://alexchen.dev", "mode": "Mode_A_Personal"}
    result = await agent.run(slice_data)

    assert "dom_snapshots" in result
    assert "visual_evidence_vnc" in result
    assert len(result["visual_evidence_vnc"]) == 1
    ev = result["visual_evidence_vnc"][0]
    assert ev.evidence_id.startswith("ev_vnc_")
    assert len(agent.execution_trace) >= 2


@pytest.mark.asyncio
async def test_audience_agent_execution():
    agent = AudienceAgent()
    slice_data = {
        "industry": "Distributed Systems",
        "target_market": ["Enterprise Decision Makers"],
        "observation_notes": "Generic developer headline without proof",
    }
    result = await agent.run(slice_data)
    assert "audience_analysis" in result
    analysis = result["audience_analysis"]
    assert "icp_profile" in analysis
    assert analysis["friction_index"] >= 5.0


@pytest.mark.asyncio
async def test_brand_agent_category_of_one():
    agent = BrandAgent()
    slice_data = {
        "mode": "Mode_A_Personal",
        "headline": "Full-Stack Developer & Passionate Problem Solver",
    }
    result = await agent.run(slice_data)
    brand = result["brand_positioning"]
    assert "category_of_one" in brand
    assert "Distributed Systems" in brand["category_of_one"]


@pytest.mark.asyncio
async def test_growth_agent_initiative_synthesis(sample_evidence):
    agent = GrowthAgent()
    slice_data = {
        "mode": "Mode_A_Personal",
        "website_url": "https://alexchen.dev",
        "visual_evidence_vnc": [sample_evidence],
    }
    result = await agent.run(slice_data)
    initiatives = result["growth_initiatives"]
    assert len(initiatives) == 1
    init: StrategicInitiative = initiatives[0]
    assert init.recommendation_id.startswith("REC-A-")
    assert init.evidence.evidence_id == sample_evidence.evidence_id
    assert init.priority.ice_score > 0.0
    assert init.approval_status == ApprovalStatus.PROPOSED


@pytest.mark.asyncio
async def test_validator_agent_adversarial_veto_on_missing_provenance(sample_strategic_initiative):
    validator = ValidatorAgent()
    init = sample_strategic_initiative
    # Set an unverified fabricated evidence ID
    init.evidence.evidence_id = "ev_fake_nonexistent_999"

    slice_data = {
        "growth_initiatives": [init],
        "research_repository": {
            "visual_evidence_vnc": [{"evidence_id": "ev_verified_123"}],
            "rag_citations": [],
        },
    }
    result = await validator.run(slice_data)
    report = result["validation_report"]
    assert report.failed_count == 1
    assert init.approval_status == ApprovalStatus.REJECTED
    assert any("Unverified evidence provenance" in r for r in (init.rejection_reasons or []))


@pytest.mark.asyncio
async def test_validator_agent_adversarial_veto_on_infeasible_metric(sample_strategic_initiative):
    validator = ValidatorAgent()
    init = sample_strategic_initiative
    # Set an absurd KPI target (e.g. 1000% lift)
    init.success_metric = SuccessMetric(
        kpi="Inbound Lead CVR",
        baseline="1.0%",
        target="15.0%",  # 1400% lift
        verification_source="GA4",
    )

    slice_data = {
        "growth_initiatives": [init],
        "research_repository": {
            "visual_evidence_vnc": [{"evidence_id": init.evidence.evidence_id}],
        },
    }
    result = await validator.run(slice_data)
    report = result["validation_report"]
    assert report.failed_count == 1
    assert init.approval_status == ApprovalStatus.REJECTED
    assert any("Unrealistic growth lift" in r for r in (init.rejection_reasons or []))


@pytest.mark.asyncio
async def test_end_to_end_orchestrator_personal_mode(sample_brand_profile_personal):
    orchestrator = StrategyOrchestrator()
    state = await orchestrator.execute_audit(
        brand_profile=sample_brand_profile_personal,
        mode=OperationalMode.MODE_A_PERSONAL,
    )
    assert state.session_id is not None
    assert state.current_stage == "Completed"
    assert len(state.strategic_artifacts.growth_initiatives) >= 1
    assert state.validation_report.passed_count >= 1

    dossier = orchestrator.compile_final_strategy_dossier(state)
    assert dossier["brand_name"] == sample_brand_profile_personal.brand_name
    assert len(dossier["approved_initiatives"]) >= 1


def test_agent_rbac_sandbox_permissions():
    analyst = AnalystAgent()
    # Agent 1 has VNC sandbox permissions
    assert analyst.verify_sandbox_access("vnc") is True
    assert analyst.verify_sandbox_access("display") is True

    # Agent 2 has no sandbox access
    audience = AudienceAgent()
    with pytest.raises(PermissionError) as exc_info:
        audience.verify_sandbox_access("vnc")
    assert "RBAC Policy Violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_supervisor_delegation_and_trace(sample_brand_profile_personal):
    orchestrator = StrategyOrchestrator()
    # Verify Agent 0 whitelisted tools
    assert "delegate_task" in orchestrator.whitelisted_tool_names
    assert "merge_agent_payload" in orchestrator.whitelisted_tool_names
    assert "route_revisions" in orchestrator.whitelisted_tool_names

    state = await orchestrator.execute_audit(
        brand_profile=sample_brand_profile_personal,
        mode=OperationalMode.MODE_A_PERSONAL,
    )
    # Verify supervisor recorded execution trace steps
    assert len(orchestrator.execution_trace) >= 6
    actions = [step["action"] for step in orchestrator.execution_trace]
    assert "delegate_task" in actions


@pytest.mark.asyncio
async def test_antigravity_runtime_harness(sample_brand_profile_personal):
    from src.orchestrator.manager import (
        AntigravityRuntimeHarness,
        CapabilitiesConfig,
        LocalAgentConfig,
    )

    capabilities = CapabilitiesConfig(
        allow_vnc_sandbox=True,
        whitelisted_tools=["delegate_task", "compile_strategy_dossier"],
    )
    config = LocalAgentConfig(
        system_instructions="Master supervisor configuration",
        capabilities=capabilities,
    )
    assert config.capabilities.allow_vnc_sandbox is True

    harness = AntigravityRuntimeHarness()
    state = await harness.execute_governed_pipeline(
        brand_profile=sample_brand_profile_personal,
        mode=OperationalMode.MODE_A_PERSONAL,
    )
    assert state.current_stage == "Completed"
    assert state.validation_report.passed_count >= 1


def test_typed_context_slices(sample_master_state):
    from src.orchestrator.context_isolator import ContextIsolator
    from src.schemas.state import AnalystSlice, AudienceSlice, GrowthSlice

    analyst_model = ContextIsolator.get_analyst_slice_model(sample_master_state)
    assert isinstance(analyst_model, AnalystSlice)
    assert analyst_model.website_url == str(sample_master_state.brand_profile.website_url)

    audience_model = ContextIsolator.get_audience_slice_model(sample_master_state)
    assert isinstance(audience_model, AudienceSlice)

    growth_model = ContextIsolator.get_growth_slice_model(sample_master_state)
    assert isinstance(growth_model, GrowthSlice)


@pytest.mark.asyncio
async def test_long_term_memory_session_persistence(sample_master_state):
    from src.memory.long_term import LongTermMemory

    memory = LongTermMemory()
    await memory.connect()
    session_id = sample_master_state.session_id
    tenant_id = "tenant_test_persistence"

    await memory.save_session_state(
        session_id=session_id,
        tenant_id=tenant_id,
        state_data=sample_master_state.model_dump(),
    )

    loaded = await memory.get_session_state(session_id=session_id, tenant_id=tenant_id)
    assert loaded is not None
    assert loaded["session_id"] == session_id
    assert loaded["brand_profile"]["brand_name"] == sample_master_state.brand_profile.brand_name
