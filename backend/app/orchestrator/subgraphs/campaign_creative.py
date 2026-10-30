from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.idempotency import generate_schedule_idempotency_key
from app.orchestrator.state import CampaignBlueprint, MarketingOSState, PlatformAssetSpec
from langgraph.graph import END, START, StateGraph


async def creative_planner_node(state: MarketingOSState) -> dict[str, Any]:
    """Plan-and-Solve blueprint generation producing multi-platform copy specs.

    Adapts messaging if critique_history is present.
    """
    campaign_id = state.get("campaign_id", "demo_camp")
    critique_history = state.get("critique_history", [])
    scheduled_utc = datetime.now(UTC) + timedelta(days=1)

    positioning = "Autonomous marketing with human control and zero hallucinations."
    if critique_history:
        positioning += f" (Revised per feedback: {critique_history[-1]})"

    platforms: list[Any] = ["linkedin", "youtube", "instagram", "x"]
    assets: list[PlatformAssetSpec] = []
    for platform in platforms:
        idempotency_key = generate_schedule_idempotency_key(
            campaign_id=campaign_id,
            platform=platform,
            scheduled_utc=scheduled_utc,
        )
        assets.append(
            PlatformAssetSpec(
                platform=platform,
                copy_text=f"Strategic update for {platform}: {positioning}",
                media_urls=[f"https://minio.marketing.internal/{campaign_id}/{platform}_preview.png"],
                aspect_ratio="1:1" if platform in ("linkedin", "instagram") else "16:9",
                scheduled_utc=scheduled_utc,
                idempotency_key=idempotency_key,
                compliance_passed=True,
            )
        )

    blueprint = CampaignBlueprint(
        campaign_id=campaign_id,
        objective="Q4 Brand Engagement & Demo Signups",
        positioning_statement=positioning,
        target_audience_segments=["B2B SaaS Executives", "Growth Leaders"],
        platform_assets=assets,
    )

    return {
        "campaign_blueprint": blueprint.model_dump(mode="json"),
        "approval_status": "pending",
    }


builder = StateGraph(MarketingOSState)
builder.add_node("creative_planner", creative_planner_node)
builder.add_edge(START, "creative_planner")
builder.add_edge("creative_planner", END)

campaign_creative_subgraph = builder.compile()
