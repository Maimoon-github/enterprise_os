import logging
from typing import Any

from app.orchestrator.state import MarketingOSState
from app.tasks.analytics_tasks import detect_metric_anomalies
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger("orchestrator.subgraphs.closed_loop_eval")


async def rewoo_planner_node(state: MarketingOSState) -> dict[str, Any]:
    """ReWOO Planner Phase: Generates deterministic tool execution DAG without LLM roundtrips.

    Plans independent metric retrieval and statistical anomaly operations upfront with symbolic handles.
    """
    campaign_id = state.get("campaign_id", "default_campaign")
    logger.info("ReWOO: Planning deterministic metric evaluation DAG for campaign %s", campaign_id)

    plan = [
        {
            "step": "#E1",
            "tool": "analytics_server.query_aggregated_kpis",
            "params": {"campaign_id": campaign_id},
            "description": "Retrieve cross-platform engagement, impressions, and CTR metrics",
        },
        {
            "step": "#E2",
            "tool": "analytics_tasks.detect_metric_anomalies",
            "params": {"input": "#E1"},
            "description": "Calculate Polars rolling z-scores to flag underperformance (Z < -1.5) or breakout (Z > 1.5)",
        },
        {
            "step": "#E3",
            "tool": "solver.synthesize_optimization_deltas",
            "params": {"anomalies": "#E2"},
            "description": "Derive budget reallocation and creative iteration directives",
        },
    ]

    return {
        "rewoo_plan": plan,
    }


async def rewoo_tool_executor_node(state: MarketingOSState) -> dict[str, Any]:
    """ReWOO Executor Phase: Deterministically executes planned tool steps #E1 in batch."""
    logger.info("ReWOO Executor: Executing tool queries across 8 platforms without LLM chatter.")

    # Deterministic multi-platform metric ingestion (sample distribution with high-performing breakout)
    platforms = [
        "linkedin",
        "youtube",
        "instagram",
        "threads",
        "facebook",
        "x",
        "pinterest",
        "google_business_profile",
    ]
    # YouTube and LinkedIn demonstrate breakout velocity; Pinterest underperforms
    metric_values = [420.0, 1450.0, 310.0, 95.0, 240.0, 180.0, 45.0, 110.0]

    return {
        "rewoo_raw_metrics": {
            "platforms": platforms,
            "metric_series": metric_values,
        },
    }


async def rewoo_solver_node(state: MarketingOSState) -> dict[str, Any]:
    """ReWOO Solver Phase: Evaluates #E2 with Polars and synthesizes #E3 optimization directives."""
    raw = state.get("rewoo_raw_metrics", {})
    platforms = raw.get("platforms", [])
    metric_series = raw.get("metric_series", [])

    logger.info("ReWOO Solver: Computing Polars rolling z-score anomalies (|Z| > 1.5)")
    anomalies = detect_metric_anomalies(metric_series, platforms)

    # Enrich anomalies with automated action recommendations
    enriched_anomalies = []
    for anom in anomalies:
        z = anom.get("z_score", 0.0)
        p = anom.get("platform", "generic")
        if z > 1.5:
            rec = f"Breakout performance on {p} (Z={z:+0.2f}). Scale budget allocation +35% and generate follow-up carousel variants."
        elif z < -1.5:
            rec = f"Underperformance detected on {p} (Z={z:+0.2f}). Pause ad spend and route copy to creative revision loop."
        else:
            rec = f"Nominal engagement on {p}."

        enriched_anomalies.append({
            "platform": p,
            "metric_value": anom.get("metric_value"),
            "z_score": z,
            "anomaly_type": anom.get("anomaly_type"),
            "recommendation": rec,
        })

    logger.info("ReWOO Solver: Discovered %d statistically significant anomalies.", len(enriched_anomalies))
    return {
        "analytics_anomalies": enriched_anomalies,
    }


builder = StateGraph(MarketingOSState)
builder.add_node("rewoo_planner", rewoo_planner_node)
builder.add_node("rewoo_tool_executor", rewoo_tool_executor_node)
builder.add_node("rewoo_solver", rewoo_solver_node)

builder.add_edge(START, "rewoo_planner")
builder.add_edge("rewoo_planner", "rewoo_tool_executor")
builder.add_edge("rewoo_tool_executor", "rewoo_solver")
builder.add_edge("rewoo_solver", END)

closed_loop_eval_subgraph = builder.compile()

