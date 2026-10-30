from typing import Any

from app.orchestrator.state import MarketingOSState, PlatformType
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

TARGET_PLATFORMS: list[PlatformType] = [
    "linkedin", "youtube", "instagram", "threads",
    "facebook", "x", "pinterest", "google_business_profile"
]

def dispatch_platform_fanout(state: MarketingOSState):
    # Map-Reduce parallel distribution using LangGraph Send()
    return [
        Send("publish_platform_worker", {"platform": platform, "campaign_id": state.get("campaign_id")})
        for platform in TARGET_PLATFORMS
    ]

async def publish_platform_worker(state: MarketingOSState) -> dict[str, Any]:
    platform = state.get("platform", "generic")
    campaign_id = state.get("campaign_id", "unknown")
    return {
        "platform_publish_results": [{
            "platform": platform,
            "status": "published",
            "post_id": f"{platform}_post_{campaign_id}",
            "idempotency_key": f"{platform}_key",
        }]
    }

builder = StateGraph(MarketingOSState)
builder.add_node("publish_platform_worker", publish_platform_worker)
builder.add_conditional_edges(START, dispatch_platform_fanout, ["publish_platform_worker"])
builder.add_edge("publish_platform_worker", END)

publishing_fanout_subgraph = builder.compile()
