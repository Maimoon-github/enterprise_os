from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from app.orchestrator.state import MarketingOSState
from app.orchestrator.routing import supervisor_router
from app.orchestrator.subgraphs.research_strategy import research_strategy_subgraph
from app.orchestrator.subgraphs.campaign_creative import campaign_creative_subgraph
from app.orchestrator.subgraphs.publishing_fanout import publishing_fanout_subgraph
from app.orchestrator.subgraphs.closed_loop_eval import closed_loop_eval_subgraph

async def human_approval_gate(state: MarketingOSState) -> Command:
    # 3-Node durable interrupt boundary
    decision = interrupt({
        "message": "Human approval required for campaign blueprint.",
        "campaign_blueprint": state.get("campaign_blueprint"),
    })
    if decision.get("approved"):
        return Command(goto="publishing_fanout", update={"approval_status": "approved"})
    return Command(goto="campaign_creative", update={"approval_status": "rejected", "critique_history": [decision.get("notes", "Revision requested")]})

builder = StateGraph(MarketingOSState)

builder.add_node("research_strategy", research_strategy_subgraph)
builder.add_node("campaign_creative", campaign_creative_subgraph)
builder.add_node("human_approval_gate", human_approval_gate)
builder.add_node("publishing_fanout", publishing_fanout_subgraph)
builder.add_node("closed_loop_eval", closed_loop_eval_subgraph)

builder.add_conditional_edges(
    START,
    supervisor_router,
    {
        "research_strategy": "research_strategy",
        "campaign_creative": "campaign_creative",
        "human_approval_gate": "human_approval_gate",
        "publishing_fanout": "publishing_fanout",
        "closed_loop_eval": "closed_loop_eval",
        "__end__": END,
    }
)

builder.add_edge("research_strategy", "campaign_creative")
builder.add_edge("campaign_creative", "human_approval_gate")
builder.add_edge("publishing_fanout", "closed_loop_eval")
builder.add_edge("closed_loop_eval", END)

master_orchestrator_graph = builder.compile()
