from typing import Literal

from app.orchestrator.state import MarketingOSState


def supervisor_router(state: MarketingOSState) -> Literal[
    "research_strategy",
    "strategy_approval_gate_node",
    "campaign_creative",
    "prepare_publish_payload_node",
    "human_approval_gate_node",
    "execute_platform_publish_node",
    "closed_loop_eval",
    "optimization_approval_gate_node",
    "__end__",
]:
    """Conditional router determining the next sub-graph or gate node in the marketing OS lifecycle."""
    if not state.get("research_dossier"):
        return "research_strategy"
    if state.get("require_strategy_approval") and not state.get("strategy_approved"):
        return "strategy_approval_gate_node"
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
    if state.get("require_optimization_approval") and not state.get("optimization_approved"):
        return "optimization_approval_gate_node"
    return "__end__"
