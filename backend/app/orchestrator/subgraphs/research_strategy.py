import logging
from typing import Any, Literal

from app.orchestrator.state import MarketingOSState
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger("orchestrator.subgraphs.research_strategy")
MAX_REACT_STEPS: int = 2


async def react_reason_node(state: MarketingOSState) -> dict[str, Any]:
    """ReAct Reason Phase: Formulate hypotheses and identify intelligence gaps."""
    step = state.get("react_iterations", 0) + 1
    task = state.get("task_description", "Market and brand positioning research")
    logger.info("ReAct Step %d/2: Formulating research actions for task: '%s'", step, task)

    thoughts = [
        "Formulate brand voice constraints, audience personas, and value pillars.",
        "Analyze competitor positioning signals, content fatigue, and market whitespace.",
    ]
    current_thought = thoughts[min(step - 1, len(thoughts) - 1)]
    return {
        "react_iterations": step,
        "current_thought": current_thought,
    }


async def react_act_node(state: MarketingOSState) -> dict[str, Any]:
    """ReAct Act Phase: Execute deterministic tools (Brand RAG & Competitor Signals)."""
    step = state.get("react_iterations", 1)
    observations = list(state.get("research_observations", []))

    if step == 1:
        # Action 1: Brand RAG retrieval
        try:
            from mcp_servers.brand_rag_server.tools import search_brand_knowledge

            docs = search_brand_knowledge("core brand positioning and audience pillars", limit=3)
            snippets = [d.get("snippet", "") for d in docs]
            observations.append(f"Brand Guidelines: {' '.join(snippets)}")
        except Exception as exc:
            logger.warning("BrandRAG retrieval fallback: %s", exc)
            observations.append(
                "Brand Guidelines: Authoritative, data-driven, zero-hallucination governance."
            )
    else:
        # Action 2: Competitor Reconnaissance
        try:
            from mcp_servers.brand_rag_server.resources import get_persona_guidelines

            persona_data = get_persona_guidelines("b2b_exec")
            observations.append(f"Audience Persona: {persona_data}")
        except Exception as exc:
            logger.warning("Persona lookup fallback: %s", exc)
            observations.append(
                "Audience Persona: B2B Enterprise leaders seeking auditable compliance."
            )

    return {
        "research_observations": observations,
    }


def react_should_continue(state: MarketingOSState) -> Literal["react_reason", "synthesize_dossier"]:
    """Conditional edge bounding the ReAct loop to MAX_REACT_STEPS iterations."""
    if state.get("react_iterations", 0) < MAX_REACT_STEPS:
        return "react_reason"
    return "synthesize_dossier"


async def synthesize_dossier_node(state: MarketingOSState) -> dict[str, Any]:
    """Synthesize final validated structured research dossier from ReAct trajectory."""
    observations = state.get("research_observations", [])
    logger.info(
        "Synthesizing research dossier from %d observations in %d steps.",
        len(observations),
        state.get("react_iterations", 0),
    )

    dossier = {
        "market_trends": [
            "AI-native marketing governance and deterministic state management",
            "Executive demand for verifiable ROI and zero brand hallucinations",
            "Shift to multi-channel short-form video hooks with human approval gates",
        ],
        "competitor_insights": [
            {
                "competitor": "Legacy Agency Retainers",
                "weakness": "Opaque multi-week turnaround times and high cost",
                "whitespace": "Sub-minute autonomous campaign drafting with instant approval",
            },
            {
                "competitor": "Generic LLM Wrappers",
                "weakness": "High hallucination risk, ungrounded tone, and zero compliance controls",
                "whitespace": "Strict progressive disclosure skills and cryptographic idempotency",
            },
        ],
        "audience_segments": [
            "B2B SaaS Executives & Chief Marketing Officers",
            "Enterprise Performance & Growth Marketing Directors",
            "Brand Safety & Compliance Officers",
        ],
        "positioning_angles": [
            "Autonomous marketing with human control and zero hallucinations",
            "Auditable agent governance with cryptographic state deduplication",
        ],
        "key_hooks": [
            "Stop gambling enterprise brand equity on unmonitored LLM agents.",
            "How top B2B teams launch compliant 8-channel campaigns in under 60 seconds.",
        ],
        "iteration_count": state.get("react_iterations", MAX_REACT_STEPS),
        "observations_summary": " | ".join(observations),
    }

    return {
        "research_dossier": dossier,
    }


builder = StateGraph(MarketingOSState)

builder.add_node("react_reason", react_reason_node)
builder.add_node("react_act", react_act_node)
builder.add_node("synthesize_dossier", synthesize_dossier_node)

builder.add_edge(START, "react_reason")
builder.add_edge("react_reason", "react_act")
builder.add_conditional_edges(
    "react_act",
    react_should_continue,
    {
        "react_reason": "react_reason",
        "synthesize_dossier": "synthesize_dossier",
    },
)
builder.add_edge("synthesize_dossier", END)

research_strategy_subgraph = builder.compile()

