from typing import Any

from app.api.deps import get_current_user, require_role
from app.core.rbac import UserRole
from app.schemas.agent import AgentConfigUpdate, AgentSummary
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("", response_model=list[AgentSummary])
async def list_agents(current_user: dict[str, Any] = Depends(get_current_user)):
    return [
        AgentSummary(
            id="agent_supervisor",
            name="Master Orchestrator Supervisor",
            model="ollama:llama3.3:70b",
            role="Global Routing & Approval Governance",
            active_workers=4,
            status="online",
        ),
        AgentSummary(
            id="agent_research",
            name="Research & Recon Specialist",
            model="ollama:qwen2.5:14b",
            role="Brand RAG Retrieval & Playwright Scraping",
            active_workers=1,
            status="online",
        ),
        AgentSummary(
            id="agent_creative",
            name="Creative Blueprint Architect",
            model="ollama:llama3.3:70b",
            role="Plan-and-Solve Copy & Media Dispatches",
            active_workers=2,
            status="online",
        ),
        AgentSummary(
            id="agent_fanout",
            name="Multi-Platform Fan-Out Worker",
            model="ollama:qwen2.5:14b",
            role="Map-Reduce Publishing to 8 Channels",
            active_workers=8,
            status="online",
        ),
        AgentSummary(
            id="agent_analytics",
            name="Closed-Loop Analytics Evaluator",
            model="ollama:qwen2.5:14b",
            role="ReWOO Polars Z-Score Anomaly Ingestion",
            active_workers=1,
            status="online",
        ),
    ]


@router.patch("/{agent_id}/config", response_model=dict[str, Any])
async def update_agent_config(
    agent_id: str,
    payload: AgentConfigUpdate,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN)),
):
    return {
        "status": "updated",
        "agent_id": agent_id,
        "config": payload.model_dump(exclude_unset=True),
    }
