from typing import Any, Literal

from app.core.idempotency import generate_schedule_idempotency_key
from app.observability.otel import (
    SPAN_KIND_AGENT,
    SPAN_KIND_CHAIN,
    SPAN_KIND_EVALUATOR,
    openinference_span,
)
from app.orchestrator.checkpointer import DynamicCheckpointer, get_checkpointer
from app.orchestrator.routing import supervisor_router
from app.orchestrator.state import MarketingOSState
from app.orchestrator.subgraphs.campaign_creative import campaign_creative_subgraph
from app.orchestrator.subgraphs.closed_loop_eval import closed_loop_eval_subgraph
from app.orchestrator.subgraphs.publishing_fanout import publishing_fanout_subgraph
from app.orchestrator.subgraphs.research_strategy import research_strategy_subgraph
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

DEFAULT_RECURSION_LIMIT: int = 25


async def research_strategy_node(state: MarketingOSState) -> dict[str, Any]:
    """Execute research strategy subgraph and return isolated research dossier."""
    with openinference_span(
        "research_strategy",
        span_kind=SPAN_KIND_AGENT,
        session_id=state.get("thread_id"),
        attributes={"agent.name": "research_strategy", "graph.node.id": "research_strategy"},
    ):
        out = await research_strategy_subgraph.ainvoke(state)
        return {
            "research_dossier": out.get("research_dossier", {}),
        }


async def campaign_creative_node(state: MarketingOSState) -> dict[str, Any]:
    """Execute creative planner subgraph and return updated blueprint without duplicating reduced channels."""
    with openinference_span(
        "campaign_creative",
        span_kind=SPAN_KIND_AGENT,
        session_id=state.get("thread_id"),
        attributes={"agent.name": "campaign_creative", "graph.node.id": "campaign_creative"},
    ):
        out = await campaign_creative_subgraph.ainvoke(state)
        return {
            "campaign_blueprint": out.get("campaign_blueprint", {}),
            "approval_status": "pending",
        }


async def prepare_publish_payload_node(state: MarketingOSState) -> dict[str, Any]:
    """Pure state transformation computing deterministic SHA-256 idempotency_key values

    and staging the review payload for human inspection.
    """
    with openinference_span(
        "prepare_publish_payload_node",
        span_kind=SPAN_KIND_CHAIN,
        session_id=state.get("thread_id"),
        attributes={"graph.node.id": "prepare_publish_payload_node"},
    ):
        blueprint = dict(state.get("campaign_blueprint") or {})
        campaign_id = state.get("campaign_id") or blueprint.get("campaign_id", "default_campaign")
        raw_assets = blueprint.get("platform_assets") or []

        validated_assets: list[dict[str, Any]] = []
        for asset in raw_assets:
            asset_dict = dict(asset) if isinstance(asset, dict) else asset.model_dump(mode="json")
            if not asset_dict.get("idempotency_key"):
                asset_dict["idempotency_key"] = generate_schedule_idempotency_key(
                    campaign_id=campaign_id,
                    platform=asset_dict.get("platform", "linkedin"),
                    scheduled_utc=asset_dict.get("scheduled_utc"),
                )
            validated_assets.append(asset_dict)

        blueprint["platform_assets"] = validated_assets
        return {
            "campaign_blueprint": blueprint,
            "approval_status": "pending",
        }


async def human_approval_gate_node(
    state: MarketingOSState,
) -> Command[Literal["execute_platform_publish_node", "campaign_creative_revision_node"]]:
    """Super-step replay-safe Human-in-the-Loop interrupt gate.

    CRITICAL SAFETY CONSTRAINT:
    Zero non-idempotent side effects or mutations exist prior to interrupt().
    Resuming re-enters this node from line 1 deterministically.
    """
    payload = {
        "message": "Human approval required for campaign blueprint.",
        "campaign_id": state.get("campaign_id"),
        "thread_id": state.get("thread_id"),
        "campaign_blueprint": state.get("campaign_blueprint"),
        "step_name": "human_approval_gate_node",
    }

    decision = interrupt(payload)

    # Post-resume deterministic branching:
    is_approved = False
    notes = "Revision requested"
    if isinstance(decision, dict):
        is_approved = bool(decision.get("approved"))
        notes = decision.get("notes") or decision.get("critique") or notes
    elif isinstance(decision, bool):
        is_approved = decision

    if is_approved:
        return Command(
            goto="execute_platform_publish_node",
            update={
                "approval_status": "approved",
                "human_approved": True,
            },
        )

    return Command(
        goto="campaign_creative_revision_node",
        update={
            "approval_status": "rejected",
            "human_approved": False,
            "critique_history": [notes],
        },
    )


# Backward compatibility alias
human_approval_gate = human_approval_gate_node


async def execute_platform_publish_node(
    state: MarketingOSState,
) -> Command[Literal["closed_loop_eval"]]:
    """Executes idempotent post-approval publishing fan-out and routes to closed_loop_eval."""
    with openinference_span(
        "execute_platform_publish_node",
        span_kind=SPAN_KIND_CHAIN,
        session_id=state.get("thread_id"),
        attributes={"graph.node.id": "execute_platform_publish_node"},
    ):
        approved_state = dict(state)
        approved_state["approval_status"] = "approved"
        approved_state["human_approved"] = True
        fanout_result = await publishing_fanout_subgraph.ainvoke(approved_state)
        publish_results = fanout_result.get("platform_publish_results", [])
        return Command(
            goto="closed_loop_eval",
            update={
                "platform_publish_results": publish_results,
                "approval_status": "approved",
                "human_approved": True,
            },
        )


async def campaign_creative_revision_node(
    state: MarketingOSState,
) -> Command[Literal["campaign_creative", "closed_loop_eval", "__end__"]]:
    """Appends critique feedback, increments revision_count, and bounds revisions (max_revisions <= 2)

    to prevent Reflexion oscillation.
    """
    current_revisions = state.get("revision_count", 0) + 1
    if current_revisions <= 2:
        return Command(
            goto="campaign_creative",
            update={
                "revision_count": current_revisions,
                "approval_status": "pending",
            },
        )
    return Command(
        goto="closed_loop_eval",
        update={
            "revision_count": current_revisions,
            "approval_status": "rejected",
        },
    )


async def closed_loop_eval_node(state: MarketingOSState) -> dict[str, Any]:
    """Execute closed loop evaluation and return anomalies."""
    with openinference_span(
        "closed_loop_eval_node",
        span_kind=SPAN_KIND_EVALUATOR,
        session_id=state.get("thread_id"),
        attributes={"graph.node.id": "closed_loop_eval_node"},
    ):
        out = await closed_loop_eval_subgraph.ainvoke(state)
        return {
            "analytics_anomalies": out.get("analytics_anomalies", []),
        }


async def strategy_approval_gate_node(
    state: MarketingOSState,
) -> Command[Literal["campaign_creative", "research_strategy"]]:
    """Super-step replay-safe Human-in-the-Loop interrupt gate for Strategy (HITL-01).

    CRITICAL SAFETY CONSTRAINT:
    Zero non-idempotent side effects exist prior to interrupt().
    Resuming re-enters this node deterministically.
    """
    payload = {
        "message": "Human approval required for research strategy and brand dossier.",
        "campaign_id": state.get("campaign_id"),
        "thread_id": state.get("thread_id"),
        "research_dossier": state.get("research_dossier"),
        "step_name": "strategy_approval_gate_node",
    }
    decision = interrupt(payload)

    is_approved = False
    notes = "Strategy revision requested"
    if isinstance(decision, dict):
        is_approved = bool(decision.get("approved"))
        notes = decision.get("notes") or notes
    elif isinstance(decision, bool):
        is_approved = decision

    if is_approved:
        return Command(
            goto="campaign_creative",
            update={
                "strategy_approved": True,
            },
        )
    return Command(
        goto="research_strategy",
        update={
            "strategy_approved": False,
            "critique_history": [notes],
        },
    )


async def optimization_approval_gate_node(
    state: MarketingOSState,
) -> Command[Literal["__end__"]]:
    """Super-step replay-safe Human-in-the-Loop interrupt gate for Optimization Proposal (HITL-03).

    CRITICAL SAFETY CONSTRAINT:
    Zero non-idempotent side effects exist prior to interrupt().
    """
    payload = {
        "message": "Human approval required for closed-loop optimization proposals and budget adjustments.",
        "campaign_id": state.get("campaign_id"),
        "thread_id": state.get("thread_id"),
        "analytics_anomalies": state.get("analytics_anomalies"),
        "step_name": "optimization_approval_gate_node",
    }
    decision = interrupt(payload)

    is_approved = False
    if isinstance(decision, dict):
        is_approved = bool(decision.get("approved"))
    elif isinstance(decision, bool):
        is_approved = decision

    return Command(
        goto="__end__",
        update={
            "optimization_approved": is_approved,
        },
    )


def route_post_research(
    state: MarketingOSState,
) -> Literal["strategy_approval_gate_node", "campaign_creative"]:
    if state.get("require_strategy_approval") and not state.get("strategy_approved"):
        return "strategy_approval_gate_node"
    return "campaign_creative"


def route_post_closed_loop(
    state: MarketingOSState,
) -> Literal["optimization_approval_gate_node", "__end__"]:
    if state.get("require_optimization_approval") and not state.get("optimization_approved"):
        return "optimization_approval_gate_node"
    return "__end__"


builder = StateGraph(MarketingOSState)

builder.add_node("research_strategy", research_strategy_node)
builder.add_node("strategy_approval_gate_node", strategy_approval_gate_node)
builder.add_node("campaign_creative", campaign_creative_node)
builder.add_node("prepare_publish_payload_node", prepare_publish_payload_node)
builder.add_node("human_approval_gate_node", human_approval_gate_node)
builder.add_node("execute_platform_publish_node", execute_platform_publish_node)
builder.add_node("campaign_creative_revision_node", campaign_creative_revision_node)
builder.add_node("publishing_fanout", publishing_fanout_subgraph)
builder.add_node("closed_loop_eval", closed_loop_eval_node)
builder.add_node("optimization_approval_gate_node", optimization_approval_gate_node)

builder.add_conditional_edges(
    START,
    supervisor_router,
    {
        "research_strategy": "research_strategy",
        "strategy_approval_gate_node": "strategy_approval_gate_node",
        "campaign_creative": "campaign_creative",
        "prepare_publish_payload_node": "prepare_publish_payload_node",
        "human_approval_gate_node": "human_approval_gate_node",
        "execute_platform_publish_node": "execute_platform_publish_node",
        "closed_loop_eval": "closed_loop_eval",
        "optimization_approval_gate_node": "optimization_approval_gate_node",
        "__end__": END,
    },
)

builder.add_conditional_edges(
    "research_strategy",
    route_post_research,
    {
        "strategy_approval_gate_node": "strategy_approval_gate_node",
        "campaign_creative": "campaign_creative",
    },
)
builder.add_edge("campaign_creative", "prepare_publish_payload_node")
builder.add_edge("prepare_publish_payload_node", "human_approval_gate_node")
builder.add_edge("publishing_fanout", "closed_loop_eval")
builder.add_conditional_edges(
    "closed_loop_eval",
    route_post_closed_loop,
    {
        "optimization_approval_gate_node": "optimization_approval_gate_node",
        "__end__": END,
    },
)
builder.add_edge("optimization_approval_gate_node", END)

MasterOrchestratorGraph = builder.compile(checkpointer=DynamicCheckpointer(get_checkpointer))
master_orchestrator_graph = MasterOrchestratorGraph
