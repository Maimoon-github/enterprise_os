from typing import Literal

from app.orchestrator.state import MarketingOSState


def supervisor_router(state: MarketingOSState) -> Literal[
    "research_strategy", "campaign_creative", "human_approval_gate", "publishing_fanout", "closed_loop_eval", "__end__"
]:
    if not state.get("research_dossier"):
        return "research_strategy"
    if not state.get("campaign_blueprint"):
        return "campaign_creative"
    if state.get("approval_status") == "pending":
        return "human_approval_gate"
    if state.get("approval_status") == "approved" and not state.get("platform_publish_results"):
        return "publishing_fanout"
    return "__end__"
