import tomllib
from pathlib import Path
import pytest
from src.agents.analyst_agent import AnalystAgent
from src.agents.audience_agent import AudienceAgent
from src.agents.base_agent import MASTER_RBAC_POLICY
from src.agents.brand_agent import BrandAgent
from src.agents.growth_agent import GrowthAgent
from src.agents.seo_content_agent import SEOContentAgent
from src.agents.validator_agent import ValidatorAgent
from src.orchestrator.manager import StrategyOrchestrator
from src.schemas.initiative import ApprovalStatus, PriorityLevel, StrategicInitiative, SuccessMetric
from src.schemas.state import OperationalMode, ReActStep


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
    assert len(result["visual_evidence_vnc"]) >= 1
    ev = result["visual_evidence_vnc"][0]
    assert ev.evidence_id.startswith("ev_vnc_")
    assert len(agent.execution_trace) >= 4


@pytest.mark.asyncio
async def test_analyst_agent_dual_viewport_mode_b_ecommerce():
    agent = AnalystAgent()
    slice_data = {
        "website_url": "https://luxuryapparel.store",
        "mode": "Mode_B_eCommerce",
        "industry": "eCommerce",
    }
    result = await agent.run(slice_data)

    assert "dom_snapshots" in result
    assert "visual_evidence_vnc" in result
    # Dual-viewport generates both Desktop and Mobile frames
    assert len(result["visual_evidence_vnc"]) == 2

    desktop_ev = result["visual_evidence_vnc"][0]
    mobile_ev = result["visual_evidence_vnc"][1]
    assert "pdp-accordion" in desktop_ev.dataset_reference
    assert "add-to-cart" in mobile_ev.dataset_reference
    assert desktop_ev.bounding_box is not None
    assert mobile_ev.bounding_box is not None

    # Verify 4-stage ReAct trace
    assert len(agent.execution_trace) == 4
    trace_actions = [step.action for step in agent.execution_trace]
    assert trace_actions == ["vnc_navigate", "extract_dom_tree", "capture_visual_evidence", "rag_query"]


@pytest.mark.asyncio
async def test_analyst_agent_rate_limiting_graceful_handling():
    agent = AnalystAgent()

    # Simulate 429 Rate Limit
    async def mock_fetch_response(url: str):
        return "<html><body>429 Too Many Requests</body></html>", 429

    agent.browser_bridge.fetch_page_response = mock_fetch_response

    slice_data = {
        "website_url": "https://rate-limited.domain.io",
        "mode": "Mode_A_Personal",
    }
    result = await agent.run(slice_data)

    assert result["visual_evidence_vnc"] == []
    assert len(result["context_gaps"]) == 1
    assert "restricted by HTTP 429" in result["context_gaps"][0]


def test_analyst_agent_whitelist_and_rbac():
    agent = AnalystAgent()
    expected_tools = {
        "vnc_navigate",
        "vnc_interact",
        "capture_visual_evidence",
        "extract_dom_tree",
        "rag_query",
    }
    assert set(agent.whitelisted_tool_names) == expected_tools

    # Attempting to register unauthorized tool triggers PermissionError
    with pytest.raises(PermissionError):
        agent.register_tool("unauthorized_shell_exec", lambda: "evil")



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
    assert analyst_model.website_url == sample_master_state.brand_profile.website_url

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


def test_master_rbac_matrix_model_profile_reconciliation():
    """Validates runtime profiles of Agents 0-6 match authoritative Master RBAC Matrix."""
    orchestrator = StrategyOrchestrator()
    assert orchestrator.model_name == "qwen2.5:14b-instruct-q4_K_M"
    assert orchestrator.temperature == 0.1
    assert orchestrator.context_window == 32768

    analyst = AnalystAgent()
    assert analyst.model_name == "llama3.2-vision:11b-instruct-q4_K_M"
    assert analyst.temperature == 0.0
    assert analyst.context_window == 16384

    audience = AudienceAgent()
    assert audience.model_name == "qwen2.5:14b-instruct-q4_K_M"
    assert audience.temperature == 0.2
    assert audience.context_window == 16384

    brand = BrandAgent()
    assert brand.model_name == "qwen2.5:14b-instruct-q4_K_M"
    assert brand.temperature == 0.2
    assert brand.context_window == 16384

    seo = SEOContentAgent()
    assert seo.model_name == "qwen2.5:14b-instruct-q4_K_M"
    assert seo.temperature == 0.2
    assert seo.context_window == 16384

    growth = GrowthAgent()
    assert growth.model_name == "qwen2.5:14b-instruct-q4_K_M"
    assert growth.temperature == 0.2
    assert growth.context_window == 32768

    validator = ValidatorAgent()
    assert validator.model_name == "deepseek-r1:32b-qwen-distill-q4_K_M"
    assert validator.temperature == 0.0
    assert validator.context_window == 32768


def test_config_toml_model_drift_reconciliation():
    """Validates .config/config.toml model configurations against Master RBAC Matrix."""
    config_path = Path(__file__).resolve().parent.parent / ".config" / "config.toml"
    assert config_path.exists(), f"Configuration file {config_path} missing"

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    models = config.get("models", {})
    assert models["orchestrator"]["name"] == "qwen2.5:14b-instruct-q4_K_M"
    assert models["orchestrator"]["temperature"] == 0.1
    assert models["orchestrator"]["context_window"] == 32768

    assert models["analyst"]["name"] == "llama3.2-vision:11b-instruct-q4_K_M"
    assert models["analyst"]["temperature"] == 0.0
    assert models["analyst"]["context_window"] == 16384

    assert models["specialist"]["name"] == "qwen2.5:14b-instruct-q4_K_M"
    assert models["specialist"]["temperature"] == 0.2
    assert models["specialist"]["context_window"] == 16384

    assert models["growth"]["name"] == "qwen2.5:14b-instruct-q4_K_M"
    assert models["growth"]["temperature"] == 0.2
    assert models["growth"]["context_window"] == 32768

    assert models["validator"]["name"] == "deepseek-r1:32b-qwen-distill-q4_K_M"
    assert models["validator"]["temperature"] == 0.0
    assert models["validator"]["context_window"] == 32768


@pytest.mark.asyncio
async def test_unauthorized_tool_invocation_rejection():
    """Verifies that invoking an unwhitelisted tool via react_step or invoke_tool raises PermissionError."""
    audience = AudienceAgent()

    # Direct invoke_tool on unauthorized tool
    with pytest.raises(PermissionError) as exc_info:
        await audience.invoke_tool("vnc_navigate", url="https://forbidden.com")
    assert "Security Violation" in str(exc_info.value)

    # react_step on unauthorized tool
    with pytest.raises(PermissionError) as exc_info:
        await audience.react_step(
            step_number=1,
            thought="Attempting unauthorized visual capture",
            action="capture_visual_evidence",
            action_args={"source_url": "https://forbidden.com"},
        )
    assert "Security Violation" in str(exc_info.value)

    # Growth agent unauthorized tool
    growth = GrowthAgent()
    with pytest.raises(PermissionError) as exc_info:
        await growth.invoke_tool("issue_veto", rec_id="REC-001", reasons=["Unwarranted"])
    assert "Security Violation" in str(exc_info.value)


def test_master_rbac_network_bridge_enforcement():
    """Validates network boundary permissions and strict denials matching Master RBAC Matrix."""
    orchestrator = StrategyOrchestrator()
    assert orchestrator.verify_network_access("internal_loopback") is True
    with pytest.raises(PermissionError) as exc_info:
        orchestrator.verify_network_access("external_internet")
    assert "RBAC Network Violation" in str(exc_info.value)

    analyst = AnalystAgent()
    assert analyst.verify_network_access("internal_vnc_sandbox") is True
    with pytest.raises(PermissionError) as exc_info:
        analyst.verify_network_access("external_internet")
    assert "RBAC Network Violation" in str(exc_info.value)

    # Specialists and Validator have network Denied
    for agent_cls in (AudienceAgent, BrandAgent, SEOContentAgent, GrowthAgent, ValidatorAgent):
        agent = agent_cls()
        with pytest.raises(PermissionError) as exc_info:
            agent.verify_network_access("internal_loopback")
        assert "RBAC Network Violation" in str(exc_info.value)
        with pytest.raises(PermissionError) as exc_info:
            agent.verify_network_access("external")
        assert "RBAC Network Violation" in str(exc_info.value)


def test_master_rbac_sandbox_boundary_granularity():
    """Validates precise sandbox permission checks per Master RBAC Matrix."""
    # Agent 0: No direct access
    orchestrator = StrategyOrchestrator()
    with pytest.raises(PermissionError):
        orchestrator.verify_sandbox_access("vnc")
    with pytest.raises(PermissionError):
        orchestrator.verify_sandbox_access("dom_snapshot")

    # Agent 1: Read-Write (Mouse, Keyboard, Display)
    analyst = AnalystAgent()
    assert analyst.verify_sandbox_access("vnc") is True
    assert analyst.verify_sandbox_access("mouse") is True
    assert analyst.verify_sandbox_access("keyboard") is True
    assert analyst.verify_sandbox_access("display") is True
    assert analyst.verify_sandbox_access("dom_snapshot") is True
    assert analyst.verify_sandbox_access("raw_evidence") is True

    # Agent 4: Read-Only (DOM snapshots)
    seo = SEOContentAgent()
    assert seo.verify_sandbox_access("dom_snapshot") is True
    with pytest.raises(PermissionError):
        seo.verify_sandbox_access("vnc")
    with pytest.raises(PermissionError):
        seo.verify_sandbox_access("raw_evidence")

    # Agent 6: Read-Only (Raw evidence blob)
    validator = ValidatorAgent()
    assert validator.verify_sandbox_access("raw_evidence") is True
    with pytest.raises(PermissionError):
        validator.verify_sandbox_access("dom_snapshot")
    with pytest.raises(PermissionError):
        validator.verify_sandbox_access("vnc")

    # Agents 2, 3, 5: Sandbox None
    for agent_cls in (AudienceAgent, BrandAgent, GrowthAgent):
        agent = agent_cls()
        with pytest.raises(PermissionError):
            agent.verify_sandbox_access("vnc")
        with pytest.raises(PermissionError):
            agent.verify_sandbox_access("dom_snapshot")
        with pytest.raises(PermissionError):
            agent.verify_sandbox_access("raw_evidence")


@pytest.mark.asyncio
async def test_deterministic_react_typed_traces():
    """Validates that all agents record execution traces composed of typed ReActStep Pydantic instances."""
    analyst = AnalystAgent()
    await analyst.run({"website_url": "https://brand.com", "mode": "Mode_A_Personal"})
    assert len(analyst.execution_trace) >= 3

    for step in analyst.execution_trace:
        assert isinstance(step, ReActStep)
        assert step.step >= 1
        assert len(step.thought) > 0  # Reason
        assert len(step.action) > 0   # Act
        assert isinstance(step.args, dict)
        assert len(step.observation) > 0  # Observe
        assert len(step.reflection) > 0   # Reflect
        # Dict access backwards-compatibility
        assert step["action"] == step.action


@pytest.mark.asyncio
async def test_mode_b_ecommerce_execution_and_guardrails(sample_evidence):
    """Validates Mode B (eCommerce) execution and specialized domain guardrails."""
    # Agent 1 eCommerce VNC reconnaissance
    analyst = AnalystAgent()
    analyst_res = await analyst.run({"website_url": "https://shop-apparel.com", "mode": "Mode_B_eCommerce"})
    assert "visual_evidence_vnc" in analyst_res
    ev = analyst_res["visual_evidence_vnc"][0]
    assert ev.dataset_reference == "div.pdp-accordion-group"

    # Agent 2 eCommerce ICP Grounding
    audience = AudienceAgent()
    aud_res = await audience.run({
        "mode": "Mode_B_eCommerce",
        "industry": "DTC Outerwear",
        "target_market": ["Active Commuters"],
        "observation_notes": "Collapsed mobile accordion menus",
    })
    icp = aud_res["audience_analysis"]["icp_profile"]
    assert "Online Shopper" in icp["title"]

    # Agent 3 eCommerce Category of One & Commodity Flagging
    brand = BrandAgent()
    brand_res = await brand.run({
        "mode": "Mode_B_eCommerce",
        "headline": "High Quality Outerwear for Everyone",
    })
    bp = brand_res["brand_positioning"]
    assert "Precision-Engineered" in bp["category_of_one"]
    assert "Commoditized" in bp["uvp_evaluation"]

    # Agent 4 eCommerce CMS-feasible SEO
    seo = SEOContentAgent()
    seo_res = await seo.run({
        "mode": "Mode_B_eCommerce",
        "dom_snapshot": {},
    })
    seo_plan = seo_res["seo_and_content_plan"]
    assert "Product" in seo_plan["technical_health"]["schema_org"]
    assert "Shopify" in seo_plan["technical_health"]["cms_feasibility"]

    # Agent 5 eCommerce Growth Synthesis
    growth = GrowthAgent()
    growth_res = await growth.run({
        "mode": "Mode_B_eCommerce",
        "website_url": "https://shop-apparel.com",
        "visual_evidence_vnc": [sample_evidence],
    })
    init = growth_res["growth_initiatives"][0]
    assert init.recommendation_id.startswith("REC-B-")
    assert "Mobile Add-to-Cart" in init.success_metric.kpi
    assert init.success_metric.verification_source == "Shopify Analytics"

