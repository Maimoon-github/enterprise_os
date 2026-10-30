from typing import Literal

from app.orchestrator.state import MarketingOSState


def supervisor_router(state: MarketingOSState) -> Literal[
    "research_strategy",
    "campaign_creative",
    "prepare_publish_payload_node",
    "human_approval_gate_node",
    "execute_platform_publish_node",
    "closed_loop_eval",
    "__end__",
]:
    """Conditional router determining the next sub-graph or gate node in the marketing OS lifecycle."""
    if not state.get("research_dossier"):
        return "research_strategy"
    if not state.get("campaign_blueprint"):
        return "campaign_creative"
    approval_status = state.get("approval_status")
    if not approval_status:
        return "prepare_publish_payload_node"
    if approval_status == "pending":
        return "human_approval_gate_node"
    if approval_status == "approved" and not state.get("platform_publish_results"):
        return "execute_platform_publish_node"
    if approval_status == "approved" and state.get("platform_publish_results") and not state.get("analytics_anomalies"):
        return "closed_loop_eval"
    return "__end__"
