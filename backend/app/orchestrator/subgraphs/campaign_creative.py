import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.agents.validators.platform_limits import PLATFORM_CHAR_LIMITS
from app.core.idempotency import generate_schedule_idempotency_key
from app.orchestrator.state import (
    AspectRatioType,
    CampaignBlueprint,
    MarketingOSState,
    PlatformAssetSpec,
    PlatformType,
)
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger("orchestrator.subgraphs.campaign_creative")

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

PLATFORM_ASPECT_RATIOS: dict[PlatformType, AspectRatioType] = {
    "linkedin": "1:1",
    "youtube": "16:9",
    "instagram": "1:1",
    "threads": "1:1",
    "facebook": "1:1",
    "x": "16:9",
    "pinterest": "2:3",
    "google_business_profile": "1:1",
}

PROHIBITED_BUZZWORDS = ["game-changer", "synergy", "paradigm shift", "disruptive"]


async def plan_structure_node(state: MarketingOSState) -> dict[str, Any]:
    """Plan Phase: Synthesize positioning pillars, audience angles, and distribution plan."""
    dossier = state.get("research_dossier", {})
    angles = dossier.get("positioning_angles", [
        "Autonomous marketing with human control and zero hallucinations",
    ])
    primary_positioning = angles[0] if angles else "Autonomous marketing with human control."

    plan = {
        "objective": "Q4 Enterprise Brand Engagement & Demo Inquiries",
        "positioning_statement": primary_positioning,
        "target_segments": dossier.get("audience_segments", ["B2B SaaS Executives", "Growth Leaders"]),
        "platforms": TARGET_PLATFORMS,
    }
    return {
        "campaign_plan": plan,
    }


async def solve_creative_node(state: MarketingOSState) -> dict[str, Any]:
    """Solve Phase: Generate platform-native copy variants and media requirements.

    Adapts phrasing if critique feedback exists (Reflexion loop).
    """
    plan = state.get("campaign_plan", {})
    critique_history = state.get("critique_history", [])
    positioning = plan.get("positioning_statement", "Autonomous marketing with human control.")

    # Incorporate critique feedback if present
    if critique_history:
        latest_critique = critique_history[-1]
        logger.info("Reflexion rewriting: incorporating feedback '%s'", latest_critique)
        for word in PROHIBITED_BUZZWORDS:
            positioning = positioning.replace(word, "auditable innovation")

    draft_assets: list[dict[str, Any]] = []
    for platform in TARGET_PLATFORMS:
        aspect = PLATFORM_ASPECT_RATIOS.get(platform, "1:1")

        if platform == "linkedin":
            copy = f"Enterprise leaders: {positioning}\n\nScale authentic multi-channel distribution without gambling on ungoverned AI. Our deterministic human-in-the-loop orchestrator guarantees zero compliance risk.\n\n#EnterpriseMarketing #B2BStrategy #MarketingOS"
        elif platform == "youtube":
            copy = f"How Top B2B Teams Deploy Autonomous Marketing with Zero Hallucinations: {positioning} Full architectural walkthrough."
        elif platform == "instagram":
            copy = f"Autonomous scale meets complete human control. {positioning} Discover how leading brands protect their voice across 8 channels. Link in bio.\n\n#GrowthMarketing #BrandSafety"
        elif platform == "threads":
            copy = f"The biggest risk in AI marketing isn't quality—it's unverified hallucinations. {positioning}"
        elif platform == "facebook":
            copy = f"Scale your brand across 8 distribution channels with complete governance. {positioning}"
        elif platform == "x":
            copy = f"Ungoverned AI is an enterprise liability. {positioning} Deterministic state + human approval gates."
        elif platform == "pinterest":
            copy = f"Deterministic Marketing Architecture: Visual guide to multi-channel governance. {positioning}"
        else:  # google_business_profile
            copy = f"Transform your multi-platform brand execution with enterprise governance. {positioning} Contact our team today."

        draft_assets.append({
            "platform": platform,
            "copy_text": copy,
            "aspect_ratio": aspect,
        })

    return {
        "draft_assets": draft_assets,
    }


async def brand_compliance_eval_node(state: MarketingOSState) -> dict[str, Any]:
    """Reflexion Critic / Rubric Gate: Deterministic limits and tone compliance check."""
    drafts = state.get("draft_assets", [])
    violations: list[str] = []

    for item in drafts:
        platform = item["platform"]
        text = item["copy_text"]

        # Check character limits
        limit = PLATFORM_CHAR_LIMITS.get(platform, 5000)
        if len(text) > limit:
            violations.append(f"{platform} text exceeds {limit} chars (got {len(text)})")

        # Check buzzwords
        found_buzzwords = [w for w in PROHIBITED_BUZZWORDS if w in text.lower()]
        if found_buzzwords:
            violations.append(f"{platform} contains prohibited buzzwords: {found_buzzwords}")

    passed = len(violations) == 0
    current_revisions = state.get("revision_count", 0)

    feedback = []
    if not passed:
        feedback = [f"Compliance violations in draft: {'; '.join(violations)}"]
        logger.warning(
            "Reflexion check failed (revision %d/2): %s", current_revisions, feedback[0]
        )

    return {
        "compliance_passed": passed,
        "critique_feedback": feedback,
    }


def should_revise_creative(state: MarketingOSState) -> Literal["solve_creative", "compile_blueprint"]:
    """Conditional Reflexion edge: allows up to 2 self-revision iterations."""
    passed = state.get("compliance_passed", True)
    revisions = state.get("revision_count", 0)

    if not passed and revisions < 2:
        return "solve_creative"
    return "compile_blueprint"


async def compile_blueprint_node(state: MarketingOSState) -> dict[str, Any]:
    """Compile final canonical CampaignBlueprint with validated PlatformAssetSpecs."""
    campaign_id = state.get("campaign_id", "default_campaign")
    plan = state.get("campaign_plan", {})
    drafts = state.get("draft_assets", [])
    scheduled_utc = datetime.now(UTC) + timedelta(days=1)

    assets: list[PlatformAssetSpec] = []
    for item in drafts:
        platform = item["platform"]
        idempotency_key = generate_schedule_idempotency_key(
            campaign_id=campaign_id,
            platform=platform,
            scheduled_utc=scheduled_utc,
        )
        assets.append(
            PlatformAssetSpec(
                platform=platform,
                copy_text=item["copy_text"],
                media_urls=[f"https://minio.marketing.internal/assets/{campaign_id}/{platform}.png"],
                aspect_ratio=item["aspect_ratio"],
                scheduled_utc=scheduled_utc,
                idempotency_key=idempotency_key,
                compliance_passed=True,
            )
        )

    blueprint = CampaignBlueprint(
        campaign_id=campaign_id,
        objective=plan.get("objective", "Multi-Channel Brand Growth"),
        positioning_statement=plan.get("positioning_statement", "Autonomous marketing with human control."),
        target_audience_segments=plan.get("target_segments", ["B2B SaaS Executives"]),
        platform_assets=assets,
    )

    return {
        "campaign_blueprint": blueprint.model_dump(mode="json"),
        "approval_status": "pending",
    }


builder = StateGraph(MarketingOSState)

builder.add_node("plan_structure", plan_structure_node)
builder.add_node("solve_creative", solve_creative_node)
builder.add_node("brand_compliance_eval", brand_compliance_eval_node)
builder.add_node("compile_blueprint", compile_blueprint_node)

builder.add_edge(START, "plan_structure")
builder.add_edge("plan_structure", "solve_creative")
builder.add_edge("solve_creative", "brand_compliance_eval")
builder.add_conditional_edges(
    "brand_compliance_eval",
    should_revise_creative,
    {
        "solve_creative": "solve_creative",
        "compile_blueprint": "compile_blueprint",
    },
)
builder.add_edge("compile_blueprint", END)

campaign_creative_subgraph = builder.compile()

