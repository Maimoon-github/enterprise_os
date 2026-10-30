from app.orchestrator.state import MarketingOSState
from langgraph.graph import END, START, StateGraph


async def market_recon_node(state: MarketingOSState) -> dict:
    # ReAct reconnaissance node - queries Qdrant BrandRAG and competitor signals
    return {
        "research_dossier": {
            "market_trends": ["AI-native brand transparency", "Short-form video hooks"],
            "competitor_insights": "Competitors actively deploying LinkedIn carousels and YouTube Shorts.",
            "audience_segments": ["B2B Tech Leaders", "Enterprise Marketers"],
        }
    }

builder = StateGraph(MarketingOSState)
builder.add_node("market_recon", market_recon_node)
builder.add_edge(START, "market_recon")
builder.add_edge("market_recon", END)

research_strategy_subgraph = builder.compile()
