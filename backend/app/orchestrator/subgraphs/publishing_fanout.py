from typing import Any

from app.core.idempotency import generate_schedule_idempotency_key
from app.orchestrator.state import MarketingOSState, PlatformType
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

TARGET_PLATFORMS: list[PlatformType] = [
    "linkedin",
    "youtube",
    "instagram",
    "threads",
    "facebook",
    "x",
    "pinterest",
    "google_business_profile",
]


def dispatch_platform_fanout(state: MarketingOSState):
    """Map-Reduce parallel distribution using LangGraph Send()."""
    campaign_id = state.get("campaign_id", "default_campaign")
    blueprint = state.get("campaign_blueprint", {})
    assets = blueprint.get("platform_assets", [])
    asset_by_platform = {a.get("platform"): a for a in assets if isinstance(a, dict)}

    tasks: list[Send] = []
    for platform in TARGET_PLATFORMS:
        asset = asset_by_platform.get(platform, {})
        tasks.append(
            Send(
                "publish_platform_worker",
                {
                    "platform": platform,
                    "campaign_id": campaign_id,
                    "scheduled_utc": asset.get("scheduled_utc"),
                    "idempotency_key": asset.get("idempotency_key"),
                },
            )
        )
    return tasks


async def publish_platform_worker(state: dict[str, Any]) -> dict[str, Any]:
    """Publish to a single platform using deterministic idempotency key."""
    platform = state.get("platform", "generic")
    campaign_id = state.get("campaign_id", "unknown")
    scheduled_utc = state.get("scheduled_utc")
    idempotency_key = state.get("idempotency_key") or generate_schedule_idempotency_key(
        campaign_id=campaign_id,
        platform=platform,
        scheduled_utc=scheduled_utc,
    )

    return {
        "platform_publish_results": [
            {
                "platform": platform,
                "status": "published",
                "post_id": f"{platform}_post_{campaign_id}",
                "idempotency_key": idempotency_key,
            }
        ]
    }


builder = StateGraph(MarketingOSState)
builder.add_node("publish_platform_worker", publish_platform_worker)
builder.add_conditional_edges(START, dispatch_platform_fanout, ["publish_platform_worker"])
builder.add_edge("publish_platform_worker", END)

publishing_fanout_subgraph = builder.compile()
