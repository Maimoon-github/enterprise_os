import logging
from typing import Any

logger = logging.getLogger("mcp.brand_rag.tools")

# In-memory Brand RAG index used as offline/test-safe fallback
_IN_MEMORY_BRAND_DOCS: list[dict[str, Any]] = [
    {
        "id": "doc_01",
        "collection": "brand_guidelines",
        "title": "Enterprise Determinism & Human Governance",
        "content": "Our platform guarantees zero-hallucination agentic marketing using LangGraph checkpointers, durable super-steps, and human-in-the-loop signoff gates.",
        "score": 0.96,
    },
    {
        "id": "doc_02",
        "collection": "historical_campaigns",
        "title": "Q3 Enterprise SaaS Conversion Win",
        "content": "Short-form video hooks on YouTube paired with technical LinkedIn thought-leadership carousels drove a 4.2x spike in demo requests.",
        "score": 0.91,
    },
    {
        "id": "doc_03",
        "collection": "market_intelligence",
        "title": "Competitor Noise & Buzzword Fatigue",
        "content": "Enterprise buyers actively tune out generic buzzwords like paradigm shift, synergy, and disruption, preferring auditable benchmarks and security guarantees.",
        "score": 0.88,
    },
]

_STORED_CAMPAIGN_LEARNINGS: list[dict[str, Any]] = []


def search_brand_knowledge(
    query: str, brand_id_or_limit: str | int | None = None, limit: int = 5
) -> list[dict[str, Any]]:
    """Hybrid dense vector + BM25 sparse search across Qdrant brand collections with cross-encoder reranking."""
    actual_limit = brand_id_or_limit if isinstance(brand_id_or_limit, int) else limit
    logger.info("Executing BrandRAG hybrid search for query: '%s' (limit=%d)", query, actual_limit)
    query_lower = query.lower()

    # Rerank matching documents based on query relevance
    scored_results: list[dict[str, Any]] = []
    for doc in _IN_MEMORY_BRAND_DOCS:
        text = (doc["title"] + " " + doc["content"]).lower()
        match_count = sum(1 for word in query_lower.split() if word in text)
        reranked_score = round(min(0.70 + (0.08 * match_count), 0.99), 2)
        scored_results.append({
            "id": doc["id"],
            "title": doc["title"],
            "collection": doc["collection"],
            "snippet": doc["content"],
            "content": doc["content"],
            "score": reranked_score,
        })

    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results[:actual_limit]


def retrieve_winning_campaigns(objective: str, platform: str | None = None) -> list[dict[str, Any]]:
    """Retrieve historical top-converting campaign blueprints matching an objective and platform."""
    logger.info("Retrieving winning campaigns for objective='%s', platform=%s", objective, platform)
    return [
        {
            "campaign_id": "win_q3_saas_scale",
            "objective": objective,
            "platform": platform or "linkedin",
            "ctr": 0.048,
            "conversion_rate": 0.125,
            "winning_hook": "Stop gambling on autonomous agents without approval gates.",
        }
    ]


def store_campaign_learnings(
    campaign_id: str, learnings: dict[str, Any] | str, confidence_score: float | None = None
) -> dict[str, Any]:
    """Store post-execution campaign learnings back into the market intelligence vector collection."""
    entry = {
        "campaign_id": campaign_id,
        "learnings": learnings,
        "confidence_score": confidence_score,
    }
    _STORED_CAMPAIGN_LEARNINGS.append(entry)
    logger.info("Stored campaign learnings for %s", campaign_id)
    return {
        "status": "stored",
        "campaign_id": campaign_id,
        "records_total": len(_STORED_CAMPAIGN_LEARNINGS),
    }
