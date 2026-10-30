from app.orchestrator.state import MarketingOSState
from langgraph.graph import END, START, StateGraph


async def creative_planner_node(state: MarketingOSState) -> dict:
    # Plan-and-Solve blueprint generation producing multi-platform copy specs
    return {
        "campaign_blueprint": {
            "campaign_id": state.get("campaign_id", "demo_camp"),
            "objective": "Q4 Brand Engagement & Demo Signups",
            "positioning_statement": "Autonomous marketing with human control and zero hallucinations.",
            "target_audience_segments": ["B2B SaaS Executives"],
        },
        "approval_status": "pending",
    }

builder = StateGraph(MarketingOSState)
builder.add_node("creative_planner", creative_planner_node)
builder.add_edge(START, "creative_planner")
builder.add_edge("creative_planner", END)

campaign_creative_subgraph = builder.compile()
