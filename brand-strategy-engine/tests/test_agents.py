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
from src.schemas.evidence import EvidenceReference
from src.schemas.initiative import ApprovalStatus, PriorityLevel, PriorityMatrix, StrategicInitiative, SuccessMetric
from src.schemas.state import (
    BrandPositioning,
    BrandSlice,
    ContentGap,
    KeywordOpportunity,
    OperationalMode,
    ReActStep,
    SEOAndContentPlan,
    SEOSlice,
    TechnicalSEOIssue,
)


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
    assert len(agent.execution_trace) == 4


def test_audience_agent_rbac_and_isolation():
    agent = AudienceAgent()
    assert agent.model_name == "qwen2.5:14b-instruct-q4_K_M"
    assert agent.temperature == 0.2
    assert agent.context_window == 16384

    # Strict whitelist
    expected_tools = {
        "query_market_demographics",
        "map_customer_journey",
        "calculate_friction",
        "rag_query",
    }
    assert set(agent.whitelisted_tool_names) == expected_tools

    # Attempting to register un-whitelisted tool raises PermissionError
    with pytest.raises(PermissionError):
        agent.register_tool("vnc_navigate", lambda: None)

    # Sandbox permissions = None -> raises PermissionError
    with pytest.raises(PermissionError) as exc_info:
        agent.verify_sandbox_access("display")
    assert "denied access to sandbox capability" in str(exc_info.value)

    # Network bridge = Denied -> raises PermissionError
    with pytest.raises(PermissionError) as exc_net:
        agent.verify_network_access("internal_vnc_sandbox")
    assert "denied network bridge access" in str(exc_net.value)

    # Alias reconciliation: friction_point_calculator
    val = agent.friction_point_calculator("Generic headline with collapsed menus")
    assert val >= 5.0


@pytest.mark.asyncio
async def test_audience_agent_react_loop_and_mode_a():
    agent = AudienceAgent()
    slice_data = {
        "industry": "Cloud Infrastructure",
        "target_market": ["VPs of Engineering", "CTOs"],
        "observation_notes": "[ev_vnc_9876] Hero section lacks quantifiable production proof",
        "visual_evidence_ids": ["ev_vnc_9876"],
        "mode": "Mode_A_Personal",
    }
    result = await agent.run(slice_data)
    assert "audience_analysis" in result
    analysis = result["audience_analysis"]

    # Verify ReAct trace: 4 stages
    assert len(agent.execution_trace) == 4
    trace_actions = [step.action for step in agent.execution_trace]
    assert trace_actions == [
        "rag_query",
        "map_customer_journey",
        "calculate_friction",
        "query_market_demographics",
    ]

    # Mode A assertions
    icp = analysis["icp_profile"]
    assert "Enterprise Technical Decision Maker" in icp["title"]
    assert "ev_vnc_9876" in icp["grounded_evidence_ids"]

    personas = analysis["buyer_personas"]
    assert len(personas) >= 1
    assert "ev_vnc_9876" in personas[0]["grounded_evidence_ids"]

    # Journey touchpoints
    touchpoints = analysis["journey_touchpoints"]
    assert len(touchpoints) == 3
    assert any("5-Sec Technical Authority" in tp["touchpoint_name"] for tp in touchpoints)


@pytest.mark.asyncio
async def test_audience_agent_mode_b_ecommerce():
    agent = AudienceAgent()
    slice_data = {
        "industry": "eCommerce Technical Apparel",
        "target_market": ["Mountain Runners"],
        "observation_notes": "[ev_vnc_5432] Sizing guides collapsed in PDP accordion; sticky ATC hides returns",
        "visual_evidence_ids": ["ev_vnc_5432"],
        "mode": "Mode_B_eCommerce",
    }
    result = await agent.run(slice_data)
    analysis = result["audience_analysis"]

    # Mode B assertions
    icp = analysis["icp_profile"]
    assert "Online Shopper" in icp["title"]
    assert "ev_vnc_5432" in icp["grounded_evidence_ids"]

    assert "Impulse" in analysis["intent_classification"] or "eCommerce" in analysis["intent_classification"]

    touchpoints = analysis["journey_touchpoints"]
    assert any("PDP" in tp["touchpoint_name"] for tp in touchpoints)
    assert any("Sticky Add-to-Cart" in tp["touchpoint_name"] for tp in touchpoints)


def test_audience_agent_persona_grounding_guardrail():
    agent = AudienceAgent()

    # Reject generic persona name "Tech Enthusiast Tim"
    generic_persona = [{
        "name": "Tech Enthusiast Tim",
        "role_archetype": "General consumer",
        "grounded_evidence_ids": ["ev_vnc_001"],
    }]
    with pytest.raises(ValueError) as exc_gen:
        agent.validate_persona_grounding(generic_persona, ["ev_vnc_001"])
    assert "Generic unanchored persona" in str(exc_gen.value)

    # Reject persona without evidence citations
    uncited_persona = [{
        "name": "VP of Engineering",
        "role_archetype": "Engineering Leader",
        "grounded_evidence_ids": [],
    }]
    with pytest.raises(ValueError) as exc_uncited:
        agent.validate_persona_grounding(uncited_persona, ["ev_vnc_001"])
    assert "no empirical evidence_id or chunk_id citation" in str(exc_uncited.value)


@pytest.mark.asyncio
async def test_audience_agent_evidence_assurance_context_gaps():
    agent = AudienceAgent()
    # Unverified / missing demographic data
    slice_data = {
        "industry": "Unknown",
        "target_market": [],
        "observation_notes": "",
    }
    result = await agent.run(slice_data)
    assert "context_gaps" in result
    assert len(result["context_gaps"]) >= 1
    assert "Demographic or intent data is unavailable" in result["context_gaps"][0]



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


def test_brand_agent_rbac_and_isolation():
    agent = BrandAgent()
    assert agent.model_name == "qwen2.5:14b-instruct-q4_K_M"
    assert agent.temperature == 0.2
    assert agent.context_window == 16384

    # Strict whitelist restricted to 4 tools
    expected_tools = {
        "extract_brand_voice",
        "benchmark_differentiation",
        "evaluate_uvp",
        "rag_query",
    }
    assert set(agent.whitelisted_tool_names) == expected_tools

    # Attempting to register un-whitelisted tool raises PermissionError
    with pytest.raises(PermissionError):
        agent.register_tool("vnc_navigate", lambda: None)

    # Sandbox permissions = None -> raises PermissionError
    with pytest.raises(PermissionError) as exc_info:
        agent.verify_sandbox_access("vnc")
    assert "denied access to sandbox capability" in str(exc_info.value)

    # Network bridge = Denied -> raises PermissionError
    with pytest.raises(PermissionError) as exc_net:
        agent.verify_network_access("internal_vnc_sandbox")
    assert "denied network bridge access" in str(exc_net.value)

    # Alias reconciliation
    voice_alias = agent.extract_brand_voice_attributes("Passionate developer and innovative builder")
    assert voice_alias["cliche_count"] >= 2
    uvp_alias = agent.uvp_clarity_evaluator("High quality products for everyone")
    assert uvp_alias["clarity_rating"] == "Deficient"
    diff_alias = agent.category_positioning_matrix_plot(["react", "python"], ["react", "node"])
    assert "react" in diff_alias["commoditized_features"]


@pytest.mark.asyncio
async def test_brand_agent_react_loop_and_mode_a():
    agent = BrandAgent()
    slice_data = {
        "mode": "Mode_A_Personal",
        "headline": "Full-Stack Developer & Passionate Problem Solver",
        "subheadings": ["Innovative Builder & Agile Team Player"],
        "visual_evidence_ids": ["ev_vnc_9876"],
    }
    result = await agent.run(slice_data)
    assert "brand_positioning" in result
    brand = result["brand_positioning"]

    # Verify 4-stage ReAct trace
    assert len(agent.execution_trace) == 4
    trace_actions = [step.action for step in agent.execution_trace]
    assert trace_actions == [
        "extract_brand_voice",
        "evaluate_uvp",
        "benchmark_differentiation",
        "rag_query",
    ]

    # Verify strongly typed Pydantic contract compliance
    pos_model = BrandPositioning(**brand)
    assert "Distributed Systems" in pos_model.category_of_one
    assert "Commoditized" in pos_model.uvp_evaluation
    assert len(pos_model.narrative_pillars) >= 2
    assert "headline" in pos_model.core_messaging_hierarchy
    assert "prescribed_position" in pos_model.differentiation_matrix
    assert len(pos_model.identity_improvement_playbook) >= 3

    # Mode A cliché detection
    assert len(pos_model.commoditized_claim_flags) >= 1
    assert any("passionate" in flag["claim"].lower() for flag in pos_model.commoditized_claim_flags)
    assert "ev_vnc_9876" in pos_model.evidence_citations


@pytest.mark.asyncio
async def test_brand_agent_mode_b_ecommerce_deep():
    agent = BrandAgent()
    slice_data = {
        "mode": "Mode_B_eCommerce",
        "headline": "High Quality Outerwear for Everyone",
        "subheadings": ["Comfortable alpine apparel made with passion"],
        "visual_evidence_ids": ["ev_vnc_ecommerce_101"],
    }
    result = await agent.run(slice_data)
    brand = result["brand_positioning"]
    pos_model = BrandPositioning(**brand)

    assert "Precision-Engineered" in pos_model.category_of_one
    assert "Commoditized" in pos_model.uvp_evaluation
    # Verify perceived value vs price tier & trust architecture
    playbook_text = " ".join(pos_model.identity_improvement_playbook).lower()
    assert "thermal" in playbook_text or "ratings" in playbook_text
    assert "trust" in playbook_text or "certifications" in playbook_text
    assert "ev_vnc_ecommerce_101" in pos_model.evidence_citations


@pytest.mark.asyncio
async def test_brand_agent_competitive_reality_guardrail():
    agent = BrandAgent()
    target_claims = ["Empirical sub-50ms distributed systems architecture", "Passionate Problem Solver"]
    competitors = [
        {
            "name": "Legacy Tech Agency",
            "headline": "Passionate Problem Solver & Full-Stack Developers",
            "messaging": "passionate problem solver",
            "evidence_id": "ev_comp_legacy_001",
        }
    ]
    flags = agent.enforce_competitive_reality(
        target_claims=target_claims,
        competitors=competitors,
        target_evidence_id="ev_vnc_test_01",
    )
    # The matching claim must be flagged as commoditized with both evidence IDs cited
    assert len(flags) == 1
    flag = flags[0]
    assert flag["status"] == "commoditized"
    assert flag["target_evidence_id"] == "ev_vnc_test_01"
    assert flag["competitor_evidence_id"] == "ev_comp_legacy_001"
    assert "Passionate Problem Solver" in flag["claim"]


@pytest.mark.asyncio
async def test_brand_agent_evidence_assurance_context_gaps():
    agent = BrandAgent()
    # Missing visual evidence and RAG citations should log context gaps
    slice_data = {
        "mode": "Mode_A_Personal",
        "headline": "",
    }
    result = await agent.run(slice_data)
    assert "context_gaps" in result
    assert len(result["context_gaps"]) >= 1
    assert any("Empirical brand visual evidence is unavailable" in g for g in result["context_gaps"])

    # Reject ungrounded citations without ev_ or chk_
    with pytest.raises(ValueError) as exc_info:
        agent.validate_evidence_assurance(["fabricated_claim_123"])
    assert "Evidence Assurance Violation" in str(exc_info.value)


def test_seo_agent_rbac_and_isolation():
    agent = SEOContentAgent()
    assert agent.model_name == "qwen2.5:14b-instruct-q4_K_M"
    assert agent.temperature == 0.2
    assert agent.context_window == 16384

    # Whitelist strictly restricted to 4 tools
    expected_tools = {
        "analyze_onpage_elements",
        "cluster_serp_intent",
        "scan_content_gaps",
        "rag_query",
    }
    assert set(agent.whitelisted_tool_names) == expected_tools

    # Attempting to register un-whitelisted tool raises PermissionError
    with pytest.raises(PermissionError):
        agent.register_tool("vnc_navigate", lambda: None)

    # Sandbox permissions: Read-only (DOM snapshots) -> dom_snapshot allowed, vnc denied
    assert agent.verify_sandbox_access("dom_snapshot") is True
    with pytest.raises(PermissionError) as exc_vnc:
        agent.verify_sandbox_access("vnc")
    assert "denied access to sandbox capability" in str(exc_vnc.value)

    # Network bridge: Denied -> raises PermissionError
    with pytest.raises(PermissionError) as exc_net:
        agent.verify_network_access("external")
    assert "denied network bridge access" in str(exc_net.value)

    # Alias reconciliation
    onpage_alias = agent.technical_seo_auditor(crawl_data={"metadata": {"title": "Short"}})
    assert "title_tag_status" in onpage_alias
    serp_alias = agent.serp_intent_cluster_analyzer(keywords=["hire distributed engineer"])
    assert len(serp_alias["high_intent_clusters"]) >= 1
    gap_alias = agent.content_gap_scanner(
        target_inventory=["portfolio"],
        competitor_inventory=["case study", "portfolio"],
    )
    assert "missing_case_studies" in gap_alias


@pytest.mark.asyncio
async def test_seo_agent_react_loop_and_mode_a():
    agent = SEOContentAgent()
    slice_data = {
        "mode": "Mode_A_Personal",
        "dom_snapshot": {
            "metadata": {
                "title": "Alex Chen | Portfolio",
                "headings": [{"level": "h1", "text": "Full-Stack Developer"}],
            },
            "evidence_id": "ev_dom_alexchen_001",
        },
    }
    result = await agent.run(slice_data)
    assert "seo_and_content_plan" in result
    plan = result["seo_and_content_plan"]

    # Verify 4-stage ReAct trace
    assert len(agent.execution_trace) == 4
    trace_actions = [step.action for step in agent.execution_trace]
    assert trace_actions == [
        "analyze_onpage_elements",
        "cluster_serp_intent",
        "scan_content_gaps",
        "rag_query",
    ]

    # Verify strongly typed Pydantic contract compliance
    plan_model = SEOAndContentPlan(**plan)
    assert "Person" in plan_model.technical_health["schema_org"]
    assert "WordPress" in plan_model.technical_health["cms_feasibility"] or "Next.js" in plan_model.technical_health["cms_feasibility"]
    assert len(plan_model.technical_issue_log) >= 3
    assert len(plan_model.keyword_opportunity_matrix) >= 3
    assert len(plan_model.content_gap_inventory) >= 2
    assert len(plan_model.content_editorial_blueprint) >= 2

    # Verify technical grounding: exact DOM node selector and evidence_id cited
    for issue in plan_model.technical_issue_log:
        assert issue.dom_selector.startswith("head >") or issue.dom_selector.startswith("main >")
        assert issue.evidence_id == "ev_dom_alexchen_001"
        assert any(cms in issue.cms_feasibility.lower() for cms in ("wordpress", "shopify", "webflow", "next.js", "native"))


@pytest.mark.asyncio
async def test_seo_agent_mode_b_ecommerce_deep():
    agent = SEOContentAgent()
    slice_data = {
        "mode": "Mode_B_eCommerce",
        "dom_snapshot": {
            "metadata": {
                "title": "Alpine Technical Outerwear - Shop Mountain Jackets",
            },
            "evidence_id": "ev_dom_ecommerce_999",
        },
    }
    result = await agent.run(slice_data)
    plan = result["seo_and_content_plan"]
    plan_model = SEOAndContentPlan(**plan)

    assert "Product" in plan_model.technical_health["schema_org"]
    assert "Shopify" in plan_model.technical_health["cms_feasibility"]
    assert any("Jacket" in kw.keyword or "Outerwear" in kw.keyword for kw in plan_model.keyword_opportunity_matrix)
    assert any(kw.search_intent == "Transactional" for kw in plan_model.keyword_opportunity_matrix)
    assert "ev_dom_ecommerce_999" in plan_model.evidence_citations


def test_seo_agent_guardrails_technical_grounding_and_intent():
    agent = SEOContentAgent()

    # Technical Grounding: Reject issues lacking DOM selector
    ungrounded_issue = TechnicalSEOIssue(
        issue_id="SEO-ERR-01",
        category="Schema Markup",
        severity="Critical",
        dom_selector="",  # empty selector violates grounding
        evidence_id="ev_dom_001",
        description="Missing schema",
        actionable_fix="Add schema markup via Next.js native head",
        cms_feasibility="Next.js native markup",
    )
    with pytest.raises(ValueError) as exc_ground:
        agent.validate_technical_grounding([ungrounded_issue])
    assert "lacks an exact DOM selector" in str(exc_ground.value)

    # Technical Grounding: Reject issues lacking valid evidence_id
    uncited_issue = TechnicalSEOIssue(
        issue_id="SEO-ERR-02",
        category="Canonicalization",
        severity="Critical",
        dom_selector="head > link[rel=\"canonical\"]",
        evidence_id="invalid_no_prefix",  # missing ev_ or chk_
        description="Missing canonical",
        actionable_fix="Add canonical tag via Shopify theme",
        cms_feasibility="Shopify Liquid",
    )
    with pytest.raises(ValueError) as exc_ev:
        agent.validate_technical_grounding([uncited_issue])
    assert "lacks a valid empirical evidence_id" in str(exc_ev.value)

    # No Keyword Stuffing: Reject keywords lacking valid search intent
    stuffed_kw = KeywordOpportunity(
        keyword="cheap shoes buy best online discount",
        search_intent="Uncategorized Intent",  # invalid intent category
        target_page="/products",
    )
    with pytest.raises(ValueError) as exc_stuff:
        agent.validate_no_keyword_stuffing([stuffed_kw])
    assert "Keyword Stuffing / Intent Violation" in str(exc_stuff.value)

    # CMS Feasibility: Reject recommendations requiring non-standard infrastructure
    unfeasible_issue = TechnicalSEOIssue(
        issue_id="SEO-ERR-03",
        category="Server Infrastructure",
        severity="Critical",
        dom_selector="head > script",
        evidence_id="ev_dom_001",
        description="Edge CDN dynamic rendering required",
        actionable_fix="Deploy custom Rust WebAssembly edge server worker cluster",
        cms_feasibility="Proprietary custom edge infrastructure",
    )
    with pytest.raises(ValueError) as exc_cms:
        agent.validate_cms_feasibility([unfeasible_issue])
    assert "CMS Feasibility Violation" in str(exc_cms.value)


@pytest.mark.asyncio
async def test_seo_agent_evidence_assurance_context_gaps():
    agent = SEOContentAgent()
    slice_data = {
        "mode": "Mode_A_Personal",
        "dom_snapshot": {},  # empty snapshot
    }
    result = await agent.run(slice_data)
    assert "context_gaps" in result
    assert len(result["context_gaps"]) >= 2
    assert any("Live crawl data is absent" in g for g in result["context_gaps"])
    assert any("CMS platform stack unverified" in g for g in result["context_gaps"])


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
    from src.schemas.state import AnalystSlice, AudienceSlice, BrandSlice, GrowthSlice

    analyst_model = ContextIsolator.get_analyst_slice_model(sample_master_state)
    assert isinstance(analyst_model, AnalystSlice)
    assert analyst_model.website_url == sample_master_state.brand_profile.website_url

    audience_model = ContextIsolator.get_audience_slice_model(sample_master_state)
    assert isinstance(audience_model, AudienceSlice)

    brand_model = ContextIsolator.get_brand_slice_model(sample_master_state)
    assert isinstance(brand_model, BrandSlice)
    assert brand_model.brand_name == sample_master_state.brand_profile.brand_name
    assert len(brand_model.visual_summaries) >= 1
    # Verify raw DOM trees, terminal logs, and SEO markups are omitted from BrandSlice
    assert not hasattr(brand_model, "dom_snapshot") or getattr(brand_model, "dom_snapshot", None) is None
    assert not hasattr(brand_model, "terminal_logs")

    growth_model = ContextIsolator.get_growth_slice_model(sample_master_state)
    assert isinstance(growth_model, GrowthSlice)

    seo_model = ContextIsolator.get_seo_slice_model(sample_master_state)
    assert isinstance(seo_model, SEOSlice)
    assert seo_model.website_url == sample_master_state.brand_profile.website_url
    assert "Alex Chen" in str(seo_model.dom_snapshot)
    # Verify raw visual buffers are omitted from SEOSlice
    assert not hasattr(seo_model, "visual_evidence_vnc") or getattr(seo_model, "visual_evidence_vnc", None) is None


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
    assert "Core_Priorities" in growth_res["roadmap"]
    assert init.recommendation_id in growth_res["roadmap"]["Core_Priorities"]


@pytest.mark.asyncio
async def test_growth_agent_react_loop_and_tool_whitelisting(sample_evidence):
    """Validates 4-stage ReAct loop, tool whitelist, and alias support for Agent 5."""
    growth = GrowthAgent()

    # Tool alias test
    rec_dict = {
        "recommendation_id": "REC-A-099",
        "initiating_agent": "Agent_5_Growth",
        "finding": "Weak proof-of-work",
        "evidence": sample_evidence.model_dump(),
        "business_implication": "Low lead volume",
        "actionable_prescription": "Deploy interactive playground",
        "priority": {
            "impact": "High",
            "effort": "Low",
            "cost": "Low",
            "confidence": "90%",
            "ice_score": 8.5,
        },
        "success_metric": {
            "kpi": "Inbound Lead CVR",
            "baseline": "1.0%",
            "target": "3.0%",
            "verification_source": "GA4",
        },
        "approval_status": "Proposed",
    }
    rec_obj = await growth.invoke_tool("build_standardized_recommendation", rec_dict=rec_dict)
    assert isinstance(rec_obj, dict)
    assert rec_obj["recommendation_id"] == "REC-A-099"

    # Execution and ReAct trace verification
    slice_data = {
        "mode": "Mode_A_Personal",
        "website_url": "https://developer.io",
        "visual_evidence_vnc": [sample_evidence],
    }
    result = await growth.run(slice_data)
    assert len(growth.execution_trace) == 4
    trace_actions = [step.action for step in growth.execution_trace]
    assert trace_actions == [
        "rag_query",
        "calculate_ice_score",
        "model_growth_projection",
        "build_recommendation",
    ]
    assert "Quick_Wins" in result["roadmap"]
    assert len(result["roadmap"]["Quick_Wins"]) == 1
    assert result["roadmap"]["Quick_Wins"][0] == result["growth_initiatives"][0].recommendation_id


@pytest.mark.asyncio
async def test_growth_agent_traceability_rejection(sample_evidence):
    """Validates that initiatives citing ungrounded evidence_ids trigger deterministic Traceability rejection."""
    growth = GrowthAgent()
    init = StrategicInitiative(
        recommendation_id="REC-A-002",
        initiating_agent=growth.agent_id,
        finding="Unsubstantiated claim",
        evidence=EvidenceReference(
            evidence_id="ev_disconnected_ghost_999",
            source_url="https://site.com",
            source_type="dom_selector",
            dataset_reference="h1",
            observation_notes="Fabricated reference",
        ),
        business_implication="None",
        actionable_prescription="None",
        priority=PriorityMatrix(
            impact=PriorityLevel.HIGH,
            effort=PriorityLevel.LOW,
            cost=PriorityLevel.LOW,
            confidence="90%",
            ice_score=8.0,
        ),
        success_metric=SuccessMetric(
            kpi="Inbound Lead CVR",
            baseline="1.0%",
            target="2.5%",
            verification_source="GA4",
        ),
        approval_status=ApprovalStatus.PROPOSED,
    )
    with pytest.raises(ValueError) as exc_info:
        growth.validate_traceability([init], valid_evidence_ids=["ev_verified_001"])
    assert "Traceability Violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_growth_agent_revision_remediation(sample_evidence):
    """Validates revision handling when Validator feedback rejects an initiative."""
    growth = GrowthAgent()
    slice_data = {
        "mode": "Mode_A_Personal",
        "website_url": "https://alexchen.dev",
        "visual_evidence_vnc": [sample_evidence],
        "rejection_reasons": ["Unrealistic growth lift: 1400% exceeds 400% threshold"],
        "iteration_cycle": 1,
    }
    res = await growth.run(slice_data)
    init = res["growth_initiatives"][0]
    assert init.iteration_cycle == 2
    assert init.success_metric.target == "2.8%"


@pytest.mark.asyncio
async def test_validator_agent_tool_aliases_and_whitelisting():
    """Validates tool whitelisting, aliases (rejection notice, approval certificate), and unauthorized tool denial."""
    validator = ValidatorAgent()

    # Tool alias: issue_rejection_notice -> issue_veto
    veto_res = await validator.invoke_tool("issue_rejection_notice", rec_id="REC-A-001", reasons=["Unproven claim"])
    assert veto_res["vetoed"] is True
    assert veto_res["recommendation_id"] == "REC-A-001"

    # Tool alias: issue_approval_certificate
    cert_res = await validator.invoke_tool("issue_approval_certificate", rec_id="REC-A-001")
    assert cert_res["approved"] is True
    assert cert_res["certificate"] == "CERT-REC-A-001"

    # Unauthorized tool invocation
    with pytest.raises(PermissionError) as exc_info:
        await validator.invoke_tool("vnc_navigate", url="https://forbidden.com")
    assert "Security Violation" in str(exc_info.value)

    # Sandbox write / VNC access denial
    with pytest.raises(PermissionError):
        validator.verify_sandbox_access("vnc")
    with pytest.raises(PermissionError):
        validator.verify_sandbox_access("dom_snapshot")
    assert validator.verify_sandbox_access("raw_evidence") is True

    # Network access denial
    with pytest.raises(PermissionError):
        validator.verify_network_access("external")


@pytest.mark.asyncio
async def test_validator_agent_logical_coherence_veto(sample_strategic_initiative, sample_evidence):
    """Validates Guardrail 2 (Logical Coherence & Alignment) veto on disconnected prescription."""
    validator = ValidatorAgent()
    init = sample_strategic_initiative
    init.actionable_prescription = "None"  # Trivial / empty prescription

    slice_data = {
        "growth_initiatives": [init],
        "research_repository": {
            "visual_evidence_vnc": [sample_evidence],
        },
    }
    result = await validator.run(slice_data)
    report = result["validation_report"]
    assert report.failed_count == 1
    assert init.approval_status == ApprovalStatus.REJECTED
    assert any("Logical disconnect" in r for r in (init.rejection_reasons or []))


@pytest.mark.asyncio
async def test_validator_agent_react_execution_trace_and_report(sample_strategic_initiative, sample_evidence):
    """Validates 4-stage ReAct execution trace, AuditEntry target_agent tracking, and ValidationReport contracts."""
    validator = ValidatorAgent()
    init = sample_strategic_initiative

    slice_data = {
        "growth_initiatives": [init],
        "research_repository": {
            "visual_evidence_vnc": [sample_evidence],
        },
    }
    result = await validator.run(slice_data)
    report = result["validation_report"]
    assert report.status == "Approved"
    assert report.passed_count == 1
    assert report.failed_count == 0
    assert len(report.audit_trail) == 3

    # Check target_agent is tracked in each AuditEntry
    for entry in report.audit_trail:
        assert entry.target_agent == init.initiating_agent
        assert entry.passed is True

    # Verify ReAct trace recorded typed steps
    assert len(validator.execution_trace) == 3
    actions = [s.action for s in validator.execution_trace]
    assert actions == [
        "verify_evidence_provenance",
        "audit_logical_consistency",
        "validate_metric_feasibility",
    ]


@pytest.mark.asyncio
async def test_validator_agent_zero_hallucination_immediate_veto(sample_strategic_initiative):
    """Enforces Zero-Hallucination Policy: immediate rejection of unanchored evidence ID."""
    validator = ValidatorAgent()
    init = sample_strategic_initiative
    init.evidence.evidence_id = "ev_fabricated_hallucination_888"

    slice_data = {
        "growth_initiatives": [init],
        "research_repository": {
            "visual_evidence_vnc": [{"evidence_id": "ev_valid_screen_001"}],
            "rag_citations": [],
            "dom_snapshots": {},
        },
    }
    result = await validator.run(slice_data)
    report = result["validation_report"]

    assert report.failed_count == 1
    assert init.approval_status == ApprovalStatus.REJECTED
    assert any("ungrounded hallucination" in r for r in (init.rejection_reasons or []))
    assert any(e.check_type == "provenance_check" and not e.passed for e in report.audit_trail)


@pytest.mark.asyncio
async def test_validator_agent_logical_alignment_with_business_goals(sample_strategic_initiative, sample_evidence):
    """Verifies Check 2 logical alignment between finding, implication, and business goals."""
    validator = ValidatorAgent()
    init = sample_strategic_initiative

    slice_data = {
        "growth_initiatives": [init],
        "research_repository": {
            "visual_evidence_vnc": [sample_evidence],
        },
        "brand_profile": {
            "business_goals": ["Increase inbound high-value contracting inquiries to 4% CTR"],
        },
    }
    result = await validator.run(slice_data)
    report = result["validation_report"]
    logical_entries = [e for e in report.audit_trail if e.check_type == "logical_alignment"]
    assert len(logical_entries) == 1
    assert logical_entries[0].passed is True


@pytest.mark.asyncio
async def test_orchestrator_stage_gating_sequence(sample_brand_profile_personal):
    """Verifies strict sequential stage progression from Stage 0 through Stage 6."""
    from src.orchestrator.state_machine import PipelineStage, StateMachine
    from src.schemas.state import MasterEngineState, OperationalMode

    state = MasterEngineState(
        session_id="test-gate-seq-1",
        mode=OperationalMode.MODE_A_PERSONAL,
        brand_profile=sample_brand_profile_personal,
        current_stage=PipelineStage.INITIALIZATION.value,
    )

    # Valid progression
    assert StateMachine.can_transition(state.current_stage, PipelineStage.ANALYST.value) is True
    StateMachine.advance_stage(state)
    assert state.current_stage == PipelineStage.ANALYST.value

    # Cannot skip directly to SEO or Validator
    assert StateMachine.can_transition(state.current_stage, PipelineStage.SEO.value) is False
    assert StateMachine.can_transition(state.current_stage, PipelineStage.VALIDATOR.value) is False




