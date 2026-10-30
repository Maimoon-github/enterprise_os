from app.orchestrator.state import MarketingOSState
from langgraph.graph import END, START, StateGraph


async def rewoo_metrics_gather(state: MarketingOSState) -> dict:
    # ReWOO pipeline gathering cross-platform metrics without LLM chatter
    return {
        "analytics_anomalies": []
    }

builder = StateGraph(MarketingOSState)
builder.add_node("rewoo_metrics_gather", rewoo_metrics_gather)
builder.add_edge(START, "rewoo_metrics_gather")
builder.add_edge("rewoo_metrics_gather", END)

closed_loop_eval_subgraph = builder.compile()
