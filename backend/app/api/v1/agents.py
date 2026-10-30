from fastapi import APIRouter, Depends
from app.api.deps import get_current_user

router = APIRouter()

@router.get("")
async def list_agents(current_user: dict = Depends(get_current_user)):
    return [
        {
            "id": "agent_supervisor",
            "name": "Master Orchestrator Supervisor",
            "model": "ollama:llama3.3:70b",
            "role": "Global Routing & Approval Governance",
            "active_workers": 4,
            "status": "online",
        },
        {
            "id": "agent_research",
            "name": "Research & Recon Specialist",
            "model": "ollama:qwen2.5:14b",
            "role": "Brand RAG Retrieval & Playwright Scraping",
            "active_workers": 1,
            "status": "online",
        },
        {
            "id": "agent_creative",
            "name": "Creative Blueprint Architect",
            "model": "ollama:llama3.3:70b",
            "role": "Plan-and-Solve Copy & Media Dispatches",
            "active_workers": 2,
            "status": "online",
        },
        {
            "id": "agent_fanout",
            "name": "Multi-Platform Fan-Out Worker",
            "model": "ollama:qwen2.5:14b",
            "role": "Map-Reduce Publishing to 8 Channels",
            "active_workers": 8,
            "status": "online",
        },
        {
            "id": "agent_analytics",
            "name": "Closed-Loop Analytics Evaluator",
            "model": "ollama:qwen2.5:14b",
            "role": "ReWOO Polars Z-Score Anomaly Ingestion",
            "active_workers": 1,
            "status": "online",
        },
    ]

@router.patch("/{agent_id}/config")
async def update_agent_config(agent_id: str, payload: dict, current_user: dict = Depends(get_current_user)):
    return {"status": "updated", "agent_id": agent_id, "config": payload}
