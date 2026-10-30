import pytest
from app.orchestrator.graph import (
    DEFAULT_RECURSION_LIMIT,
    builder,
    master_orchestrator_graph,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command


@pytest.mark.asyncio
async def test_graph_initialization():
    """Verify MasterOrchestratorGraph compiles cleanly with recursion limit."""
    assert master_orchestrator_graph is not None
    assert DEFAULT_RECURSION_LIMIT == 25


@pytest.mark.asyncio
async def test_3_node_interrupt_gate_approval():
    """Verify the 3-node approval gate interrupts safely and resumes with approval."""
    test_graph = builder.compile(checkpointer=MemorySaver())
    thread_id = "test_hitl_approval_thread"
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": DEFAULT_RECURSION_LIMIT,
    }

    # 1. Initial run enters prepare_publish_payload_node and halts at human_approval_gate_node
    result = await test_graph.ainvoke(
        {"campaign_id": "camp_hitl_01", "thread_id": thread_id},
        config=config,
    )
    assert "__interrupt__" in result
    interrupts = result["__interrupt__"]
    assert len(interrupts) > 0
    payload = interrupts[0].value
    assert payload["step_name"] == "human_approval_gate_node"
    assert "campaign_blueprint" in payload

    # Verify checkpointer recorded pause state
    state = await test_graph.aget_state(config)
    assert state.next == ("human_approval_gate_node",)
    assert state.values.get("approval_status") == "pending"

    # 2. Super-step replay safety: Resume with approval
    resume_result = await test_graph.ainvoke(
        Command(resume={"approved": True, "notes": "LGTM"}),
        config=config,
    )
    assert "__interrupt__" not in resume_result

    final_state = await test_graph.aget_state(config)
    assert final_state.next == ()
    assert final_state.values.get("approval_status") == "approved"
    assert final_state.values.get("human_approved") is True
    assert len(final_state.values.get("platform_publish_results", [])) == 8


@pytest.mark.asyncio
async def test_3_node_interrupt_gate_rejection_and_bounded_reflexion():
    """Verify rejection loop appends to critique_history and bounds revisions (max_revisions <= 2)."""
    test_graph = builder.compile(checkpointer=MemorySaver())
    thread_id = "test_hitl_rejection_thread"
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": DEFAULT_RECURSION_LIMIT,
    }

    # Initial run -> Interrupt
    await test_graph.ainvoke(
        {"campaign_id": "camp_hitl_02", "thread_id": thread_id},
        config=config,
    )

    # Rejection 1 -> revisions = 1
    await test_graph.ainvoke(
        Command(resume={"approved": False, "notes": "Rewrite LinkedIn hook"}),
        config=config,
    )
    state_rev1 = await test_graph.aget_state(config)
    assert state_rev1.next == ("human_approval_gate_node",)
    assert state_rev1.values.get("revision_count") == 1
    assert "Rewrite LinkedIn hook" in state_rev1.values.get("critique_history", [])

    # Rejection 2 -> revisions = 2
    await test_graph.ainvoke(
        Command(resume={"approved": False, "notes": "Adjust tone for YouTube"}),
        config=config,
    )
    state_rev2 = await test_graph.aget_state(config)
    assert state_rev2.next == ("human_approval_gate_node",)
    assert state_rev2.values.get("revision_count") == 2
    assert len(state_rev2.values.get("critique_history", [])) == 2

    # Rejection 3 -> max_revisions (2) exceeded, graph terminates to prevent Reflexion oscillation
    await test_graph.ainvoke(
        Command(resume={"approved": False, "notes": "Still unsatisfactory"}),
        config=config,
    )
    final_state = await test_graph.aget_state(config)
    assert final_state.next == ()
    assert final_state.values.get("approval_status") == "rejected"
    assert final_state.values.get("revision_count") == 3


@pytest.mark.asyncio
async def test_research_strategy_subgraph_react_loop():
    """Verify research_strategy_subgraph executes bounded ReAct loop and returns structured dossier."""
    from app.orchestrator.subgraphs.research_strategy import research_strategy_subgraph

    state = {
        "campaign_id": "camp_react_01",
        "task_description": "Analyze enterprise AI governance market",
    }
    out = await research_strategy_subgraph.ainvoke(state)
    dossier = out.get("research_dossier", {})

    assert "market_trends" in dossier
    assert "competitor_insights" in dossier
    assert "audience_segments" in dossier
    assert "positioning_angles" in dossier
    assert "key_hooks" in dossier
    assert dossier.get("iteration_count") == 2
    assert len(dossier["market_trends"]) >= 2


@pytest.mark.asyncio
async def test_campaign_creative_subgraph_plan_and_solve_reflexion():
    """Verify campaign_creative_subgraph Plan-and-Solve with Reflexion adaptation across all 8 platforms."""
    from app.orchestrator.subgraphs.campaign_creative import campaign_creative_subgraph

    state = {
        "campaign_id": "camp_creative_01",
        "research_dossier": {
            "positioning_angles": ["Autonomous marketing with human control and zero hallucinations"],
            "audience_segments": ["B2B SaaS Executives"],
        },
        "critique_history": ["Remove buzzwords: synergy"],
        "revision_count": 0,
    }
    out = await campaign_creative_subgraph.ainvoke(state)
    blueprint = out.get("campaign_blueprint", {})

    assert blueprint.get("campaign_id") == "camp_creative_01"
    assets = blueprint.get("platform_assets", [])
    assert len(assets) == 8

    platforms = {a["platform"] for a in assets}
    assert platforms == {
        "linkedin", "youtube", "instagram", "threads",
        "facebook", "x", "pinterest", "google_business_profile"
    }

    # Verify idempotency keys and aspect ratios
    for a in assets:
        assert len(a["idempotency_key"]) == 64
        assert a["aspect_ratio"] in ("1:1", "16:9", "9:16", "2:3", "4:5")


@pytest.mark.asyncio
async def test_publishing_fanout_subgraph_map_reduce_and_guards():
    """Verify publishing_fanout_subgraph blocks unapproved execution and executes Map-Reduce on approved states."""
    from app.orchestrator.subgraphs.publishing_fanout import publishing_fanout_subgraph

    # 1. Unapproved guardrail check
    unapproved_state = {
        "campaign_id": "camp_fanout_01",
        "human_approved": False,
        "approval_status": "pending",
        "campaign_blueprint": {"platform_assets": []},
    }
    blocked_out = await publishing_fanout_subgraph.ainvoke(unapproved_state)
    assert len(blocked_out.get("platform_publish_results", [])) == 0

    # 2. Approved fan-out execution across 8 channels
    approved_state = {
        "campaign_id": "camp_fanout_01",
        "human_approved": True,
        "approval_status": "approved",
        "campaign_blueprint": {
            "platform_assets": [
                {"platform": p, "copy_text": f"Post for {p}"}
                for p in ["linkedin", "youtube", "instagram", "threads", "facebook", "x", "pinterest", "google_business_profile"]
            ]
        },
    }
    approved_out = await publishing_fanout_subgraph.ainvoke(approved_state)
    results = approved_out.get("platform_publish_results", [])
    assert len(results) == 8
    published_platforms = {r["platform"] for r in results}
    assert len(published_platforms) == 8


@pytest.mark.asyncio
async def test_closed_loop_eval_subgraph_rewoo_deterministic_dag():
    """Verify closed_loop_eval_subgraph executes deterministic ReWOO DAG and detects statistical anomalies."""
    from app.orchestrator.subgraphs.closed_loop_eval import closed_loop_eval_subgraph

    state = {
        "campaign_id": "camp_eval_01",
        "platform_publish_results": [{"platform": "youtube", "status": "published"}],
    }
    out = await closed_loop_eval_subgraph.ainvoke(state)

    assert "rewoo_plan" in out
    plan = out["rewoo_plan"]
    assert len(plan) == 3
    assert plan[0]["step"] == "#E1"
    assert plan[1]["step"] == "#E2"
    assert plan[2]["step"] == "#E3"

    anomalies = out.get("analytics_anomalies", [])
    assert len(anomalies) >= 1
    assert any(a["anomaly_type"] in ("breakout", "underperformance") for a in anomalies)
    for a in anomalies:
        assert "recommendation" in a
        assert abs(a["z_score"]) > 1.5

