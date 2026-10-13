# pyright: reportMissingImports=false
"""Validation tests for TSK-05: Hierarchical Planning, CoT/Re-Act Reasoning, and Dynamic Replanning."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from core.nodes.reasoning_node import ReActExecutionLoop, strategic_reasoning_node
from core.planning.htn_planner import HTNPlanner, MicroTask
from core.reasoning.cot_engine import (
    CoTReasoningResult,
    CoTStrategicEngine,
    DeterministicChatModel,
    ModelRouter,
    ModelTier,
)
from core.state import AgentState, AuditMetrics, BrandProfile


def test_htn_planning_decomposition():
    """Verify HTN planner decomposes goals across Macro, Meso, and Micro tiers."""
    planner = HTNPlanner(baseline_traffic=20000, target_cac=35.0)

    brand = BrandProfile(
        brand_name="AuraGlow Skincare",
        target_audience="Health-conscious Gen-Z & Millennial Shoppers",
        core_pillars=[
            "35% Educational",
            "25% Proof/Demos",
            "20% Brand Story",
            "20% Offers/Conversion",
        ],
    )

    audit = AuditMetrics(
        reach=100000,
        traffic=24000,
        conversions=700,
        cac=30.0,
        clv=120.0,
        health_ratio=4.0,
        baymard_issues=[
            "[BAYMARD-01] Forced Registration: Must offer guest checkout",
            "[BAYMARD-02] Hidden Shipping Costs: Disclose shipping upfront",
        ],
    )

    # 1. Decompose into task queue
    task_queue = planner.decompose(brand=brand, audit=audit, current_day=15)

    assert isinstance(task_queue, list)
    assert len(task_queue) >= 4

    # Verify task structure and hierarchy
    for task in task_queue:
        assert "task_id" in task
        assert task["tier"] == "micro"
        assert "parent_meso_id" in task
        assert "parent_macro_id" in task
        assert "priority" in task
        assert "action_type" in task

    # Verify Baymard friction tasks are assigned critical priority at head of queue
    first_task = task_queue[0]
    assert first_task["priority"] == "critical"
    assert "BAYMARD-01" in first_task["title"] or "Forced Registration" in first_task["title"]
    print("test_htn_planning_decomposition: PASSED")


def test_cot_strategic_engine_deliberation():
    """Verify CoT engine produces analytical reasoning for positioning trade-offs."""
    engine = CoTStrategicEngine()

    brand = BrandProfile(
        brand_name="AuraGlow Skincare",
        target_audience="D2C Skincare Shoppers",
        core_pillars=["35% Educational", "25% Proof/Demos"],
    )

    audit = AuditMetrics(
        traffic=15000,
        cac=45.0,
        clv=110.0,
        health_ratio=2.44,
        baymard_issues=["[BAYMARD-02] Hidden Shipping Costs"],
    )

    result = engine.deliberate(brand=brand, audit=audit)

    assert isinstance(result, CoTReasoningResult)
    assert result.model_tier == "high_capacity"
    assert len(result.deliberation_trace) > 50
    assert len(result.positioning_trade_offs) >= 2
    assert len(result.tactical_directives) >= 2
    assert result.confidence_score >= 0.85
    assert "AuraGlow Skincare" in result.selected_strategy
    print("test_cot_strategic_engine_deliberation: PASSED")


def test_react_execution_loop_cycle():
    """Verify Re-Act execution loop produces Thought -> Action -> Observation -> Reflection."""
    react = ReActExecutionLoop()

    micro_task = {
        "task_id": "TASK-BOFU-01",
        "title": "Resolve Baymard Hidden Shipping Costs",
        "action_type": "cro_fix",
        "parameters": {"friction_type": "shipping_fee_disclosure"},
    }

    brand = BrandProfile(brand_name="AuraGlow Skincare")
    step_result = react.execute_step(task=micro_task, brand=brand)

    assert step_result.task_id == "TASK-BOFU-01"
    assert step_result.status == "completed"
    assert len(step_result.thought) > 10
    assert len(step_result.action) > 10
    assert len(step_result.observation) > 10
    assert len(step_result.reflection) > 10
    print("test_react_execution_loop_cycle: PASSED")


def test_dynamic_replanning_triggers():
    """Verify dynamic replanner triggers upon metric deviations and restructures task_queue."""
    planner = HTNPlanner(baseline_traffic=20000, target_cac=35.0)
    brand = BrandProfile(brand_name="AuraGlow Skincare")

    # Scenario A: Healthy metrics -> No replanning needed
    healthy_audit = AuditMetrics(traffic=25000, cac=28.0, health_ratio=4.2, baymard_issues=[])
    assert planner.should_replan(healthy_audit) is False

    # Scenario B: High CAC spike (CAC=$48.0 > target $35.0) -> Triggers replanning
    cac_spike_audit = AuditMetrics(traffic=22000, cac=48.0, health_ratio=2.5, baymard_issues=[])
    assert planner.should_replan(cac_spike_audit) is True

    # Scenario C: Traffic drop (Traffic=12000 < baseline 20000) -> Triggers replanning
    traffic_drop_audit = AuditMetrics(traffic=12000, cac=32.0, health_ratio=3.5, baymard_issues=[])
    assert planner.should_replan(traffic_drop_audit) is True

    # Execute dynamic replanning
    current_queue = [
        {"task_id": "TASK-OLD-01", "title": "Standard Review", "status": "pending"},
    ]
    rebuilt_queue = planner.replan(
        current_queue=current_queue,
        audit=cac_spike_audit,
        brand=brand,
    )

    assert len(rebuilt_queue) >= 2
    task_ids = [t["task_id"] for t in rebuilt_queue]
    assert "TASK-REPLAN-CAC-01" in task_ids
    assert "TASK-OLD-01" in task_ids
    print("test_dynamic_replanning_triggers: PASSED")


def test_strategic_reasoning_node_langgraph_workflow():
    """Verify strategic_reasoning_node execution in LangGraph StateGraph."""
    brand = BrandProfile(
        brand_name="AuraGlow Skincare",
        target_audience="D2C Skincare Shoppers",
    )

    audit = AuditMetrics(
        traffic=14000,  # Below baseline 20000
        cac=42.0,   # Above target 35.0
        health_ratio=2.6,
        baymard_issues=["[BAYMARD-01] Forced Registration"],
    )

    initial_state: AgentState = {
        "messages": [HumanMessage(content="Trigger strategic reasoning node")],
        "phase": "reasoning",
        "brand_profile": brand,
        "audit_metrics": audit,
        "task_queue": [],
        "errors": [],
        "artifacts": [],
        "metadata": {"baseline_traffic": 20000, "target_cac": 35.0},
    }

    # 1. Single node execution
    output = strategic_reasoning_node(initial_state)

    assert "task_queue" in output
    assert len(output["task_queue"]) >= 3
    assert output["phase"] == "action"
    assert len(output["messages"]) == 1

    # Verify at least one task was marked completed by Re-Act core
    completed_tasks = [t for t in output["task_queue"] if t.get("status") == "completed"]
    assert len(completed_tasks) >= 1

    # 2. Assembled LangGraph StateGraph workflow execution
    workflow = StateGraph(AgentState)
    workflow.add_node("reasoning_node", strategic_reasoning_node)
    workflow.add_edge(START, "reasoning_node")
    workflow.add_edge("reasoning_node", END)

    app = workflow.compile()
    final_state = app.invoke(initial_state)

    assert final_state["phase"] == "action"
    assert len(final_state["task_queue"]) >= 3
    assert len(final_state["messages"]) == 2  # 1 human + 1 AI
    print("test_strategic_reasoning_node_langgraph_workflow: PASSED")


if __name__ == "__main__":
    test_htn_planning_decomposition()
    test_cot_strategic_engine_deliberation()
    test_react_execution_loop_cycle()
    test_dynamic_replanning_triggers()
    test_strategic_reasoning_node_langgraph_workflow()
    print("=== ALL TSK-05 TESTS PASSED ===")
