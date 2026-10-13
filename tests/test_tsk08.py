# pyright: reportMissingImports=false
"""Validation tests for TSK-08: Unit Economics, Funnel Diagnostics, and Campaign Reallocation."""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from analytics.funnel_diagnostics import (
    FunnelBottleneck,
    FunnelDiagnosticEngine,
    FunnelDiagnosticReport,
)
from analytics.unit_economics import (
    UnitEconomicsCalculator,
    UnitEconomicsMetrics,
)
from core.nodes.optimization_node import (
    CampaignReallocation,
    CampaignReallocationEngine,
    funnel_optimization_node,
)
from core.state import AgentState, AuditMetrics, BrandProfile


def test_unit_economics_sandbox_calculation():
    """Verify UnitEconomicsCalculator calculates Net Contribution, ROAS, CAC, and CLV/CAC Health Ratio."""
    calculator = UnitEconomicsCalculator()

    revenue = 100000.0
    ad_spend = 20000.0
    cogs = 30000.0
    logistics = 8000.0
    new_customers = 500
    clv = 150.0

    metrics: UnitEconomicsMetrics = calculator.calculate(
        revenue=revenue,
        ad_spend=ad_spend,
        cogs=cogs,
        logistics_fees=logistics,
        new_customers=new_customers,
        clv=clv,
    )

    # Net Contribution = 100,000 - 30,000 - 20,000 - 8,000 = 42,000
    assert metrics.revenue == 100000.0
    assert metrics.net_contribution == 42000.0
    # ROAS = 100,000 / 20,000 = 5.0
    assert metrics.roas == 5.0
    # CAC = 20,000 / 500 = 40.0
    assert metrics.cac == 40.0
    # Health Ratio = 150.0 / 40.0 = 3.75 >= 3.0
    assert metrics.health_ratio == 3.75
    assert metrics.is_healthy is True
    assert metrics.gross_margin_pct == 70.0
    assert metrics.contribution_margin_pct == 42.0

    print("test_unit_economics_sandbox_calculation: PASSED")


def test_funnel_bottleneck_diagnostics_heuristics():
    """Verify diagnostic heuristics detect ToFu, MoFu, and BoFu leakage points."""
    engine = FunnelDiagnosticEngine()

    # Case 1: High Reach + Low Traffic (CTR < 1.8%) -> ToFu Hook Issue
    tofu_audit = AuditMetrics(
        reach=100000,
        traffic=1000,
        conversions=50,
        bounce_rate=0.40,
        baymard_issues=[],
        roas=3.5,
    )
    tofu_report = engine.diagnose(audit=tofu_audit)
    stages = [b.stage for b in tofu_report.bottlenecks]
    assert "ToFu" in stages
    tofu_bottleneck = next(b for b in tofu_report.bottlenecks if b.stage == "ToFu")
    assert "hook weakness" in tofu_bottleneck.root_cause.lower() or "distribution" in tofu_bottleneck.root_cause.lower()

    # Case 2: High Traffic + Low Conversions (CVR < 2.0%) + Baymard issues -> BoFu Checkout Friction
    bofu_audit = AuditMetrics(
        reach=50000,
        traffic=10000,
        conversions=80,  # 0.8% CVR
        bounce_rate=0.45,
        baymard_issues=["Baymard-01: Hidden Shipping Fees at Final Checkout"],
        roas=2.8,
    )
    bofu_report = engine.diagnose(audit=bofu_audit)
    stages_bofu = [b in [x.stage for x in bofu_report.bottlenecks] for b in ["BoFu"]]
    assert all(stages_bofu)
    bofu_bottleneck = next(b for b in bofu_report.bottlenecks if b.stage == "BoFu")
    assert "checkout" in bofu_bottleneck.root_cause.lower() or "drop-off" in bofu_bottleneck.root_cause.lower()

    # Case 3: High Bounce Rate (> 55%) -> MoFu Consideration Leakage
    mofu_audit = AuditMetrics(
        reach=50000,
        traffic=8000,
        conversions=300,
        bounce_rate=0.68,
        baymard_issues=[],
        roas=3.0,
    )
    mofu_report = engine.diagnose(audit=mofu_audit)
    stages_mofu = [b.stage for b in mofu_report.bottlenecks]
    assert "MoFu" in stages_mofu

    print("test_funnel_bottleneck_diagnostics_heuristics: PASSED")


def test_autonomous_campaign_reallocation():
    """Verify CampaignReallocationEngine scales ROAS >= 3.5 and retires ROAS < 2.0."""
    campaigns = [
        {"campaign_id": "CMP-01", "name": "Winner Scale Campaign", "current_budget": 4000.0, "roas": 4.5},
        {"campaign_id": "CMP-02", "name": "Stable Core Campaign", "current_budget": 3000.0, "roas": 2.8},
        {"campaign_id": "CMP-03", "name": "Bleeding Creative Asset", "current_budget": 2000.0, "roas": 1.2},
    ]

    reallocations = CampaignReallocationEngine.reallocate(campaigns=campaigns, target_roas_benchmark=3.0)
    assert len(reallocations) == 3

    rec_by_id = {r.campaign_id: r for r in reallocations}

    # CMP-01: High ROAS (4.5 >= 3.5) -> SCALE
    assert rec_by_id["CMP-01"].action == "SCALE"
    assert rec_by_id["CMP-01"].new_budget > 4000.0

    # CMP-02: Moderate ROAS (2.8 in [2.0, 3.5)) -> MAINTAIN
    assert rec_by_id["CMP-02"].action == "MAINTAIN"
    assert rec_by_id["CMP-02"].new_budget == 3000.0

    # CMP-03: Low ROAS (1.2 < 2.0) -> RETIRE
    assert rec_by_id["CMP-03"].action == "RETIRE"
    assert rec_by_id["CMP-03"].new_budget == 0.0

    # Reallocated freed funds transferred to scaling campaign
    assert rec_by_id["CMP-01"].new_budget == 4000.0 * 1.35 + 2000.0

    print("test_autonomous_campaign_reallocation: PASSED")


def test_funnel_optimization_node_in_langgraph():
    """Verify execution of funnel_optimization_node within a compiled LangGraph workflow."""
    builder = StateGraph(AgentState)
    builder.add_node("optimization", funnel_optimization_node)
    builder.add_edge(START, "optimization")
    builder.add_edge("optimization", END)
    graph = builder.compile()

    state: AgentState = {
        "brand_profile": BrandProfile(
            brand_name="AuraGlow Skincare",
            target_audience="D2C Skincare Enthusiasts",
        ),
        "phase": "action",
        "messages": [HumanMessage(content="Optimize marketing funnel and unit economics for Q3.")],
        "audit_metrics": AuditMetrics(
            reach=120000,
            traffic=24000,
            conversions=600,
            bounce_rate=0.48,
            baymard_issues=["Baymard-02: Hidden shipping costs"],
            roas=3.6,
        ),
        "metadata": {
            "revenue": 120000.0,
            "ad_spend": 28000.0,
            "cogs": 36000.0,
            "logistics_fees": 9600.0,
            "new_customers": 600,
            "campaigns": [
                {"campaign_id": "CMP-A", "name": "Top Scale Ad", "current_budget": 5000.0, "roas": 4.8},
                {"campaign_id": "CMP-B", "name": "Mid Funnel Case Study", "current_budget": 3000.0, "roas": 2.9},
                {"campaign_id": "CMP-C", "name": "Weak Ad Angle", "current_budget": 2000.0, "roas": 1.1},
            ],
        },
        "errors": [],
        "artifacts": [],
    }

    final_state = graph.invoke(state)

    assert final_state["phase"] == "evaluation"
    assert "/home/gem/campaign_optimization.md" in final_state["artifacts"]
    assert final_state["audit_metrics"].health_ratio > 0
    assert final_state["audit_metrics"].roas > 0
    assert len(final_state["messages"]) > 1

    print("test_funnel_optimization_node_in_langgraph: PASSED")


if __name__ == "__main__":
    test_unit_economics_sandbox_calculation()
    test_funnel_bottleneck_diagnostics_heuristics()
    test_autonomous_campaign_reallocation()
    test_funnel_optimization_node_in_langgraph()
    print("ALL TSK-08 TESTS PASSED SUCCESSFULLY.")
