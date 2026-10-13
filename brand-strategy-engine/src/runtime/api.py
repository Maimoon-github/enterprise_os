"""FastAPI REST API runtime for Universal AI Brand Strategy Engine."""

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.orchestrator.manager import StrategyOrchestrator
from src.schemas.state import BrandProfile, MasterEngineState, OperationalMode

app = FastAPI(
    title="Universal AI Brand Strategy Engine API",
    version="2.4.0",
    description="REST interface for empirical multi-agent website audits and growth strategy synthesis.",
)

# In-memory execution store for sessions
_SESSION_STATES: Dict[str, MasterEngineState] = {}
_SESSION_TASKS: Dict[str, str] = {}
_ORCHESTRATOR = StrategyOrchestrator()


class AuditStartRequest(BaseModel):
    url: str = Field(..., description="Target brand website URL")
    brand_name: str = Field(..., description="Brand or professional client name")
    mode: OperationalMode = Field(default=OperationalMode.MODE_A_PERSONAL, description="Operational modality")
    industry: str = Field(default="Technology", description="Domain sector")
    target_market: List[str] = Field(default_factory=lambda: ["Decision Makers"])
    business_goals: List[str] = Field(default_factory=lambda: ["Improve conversion rate"])
    docs_dir: Optional[str] = Field(default=None, description="Path to uploaded client files")
    tenant_id: Optional[str] = Field(default=None, description="Multi-tenant identifier")


class AuditStartResponse(BaseModel):
    session_id: str
    status: str
    message: str


async def _run_audit_background(
    session_id: str,
    profile: BrandProfile,
    mode: OperationalMode,
    docs_dir: Optional[str],
    tenant_id: Optional[str],
):
    try:
        _SESSION_TASKS[session_id] = "Running"
        state = await _ORCHESTRATOR.execute_audit(
            brand_profile=profile,
            mode=mode,
            docs_dir=docs_dir,
            tenant_id=tenant_id,
        )
        _SESSION_STATES[session_id] = state
        _SESSION_TASKS[session_id] = "Completed"
    except Exception as e:
        _SESSION_TASKS[session_id] = f"Failed: {e}"


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health status and engine metadata."""
    return {
        "status": "healthy",
        "engine_version": "2.4.0",
        "runtime": "antigravity-local-ollama",
    }


@app.post("/api/v1/audit/start", response_model=AuditStartResponse)
async def start_audit(
    request: AuditStartRequest,
    background_tasks: BackgroundTasks,
) -> AuditStartResponse:
    """Initiates an autonomous multi-agent audit run."""
    import uuid
    session_id = str(uuid.uuid4())

    profile = BrandProfile(
        website_url=request.url,
        brand_name=request.brand_name,
        industry=request.industry,
        target_market=request.target_market,
        business_goals=request.business_goals,
    )

    _SESSION_TASKS[session_id] = "Queued"
    background_tasks.add_task(
        _run_audit_background,
        session_id=session_id,
        profile=profile,
        mode=request.mode,
        docs_dir=request.docs_dir,
        tenant_id=request.tenant_id,
    )

    return AuditStartResponse(
        session_id=session_id,
        status="Queued",
        message="Audit session initiated successfully.",
    )


@app.get("/api/v1/audit/status/{session_id}")
async def get_audit_status(session_id: str) -> Dict[str, Any]:
    """Retrieves real-time status and stage progress for an active audit."""
    if session_id not in _SESSION_TASKS:
        raise HTTPException(status_code=404, detail="Session not found")

    task_status = _SESSION_TASKS[session_id]
    state = _SESSION_STATES.get(session_id)

    return {
        "session_id": session_id,
        "task_status": task_status,
        "current_stage": state.current_stage if state else "Initializing",
        "iteration_counter": state.iteration_counter if state else 0,
        "validation_status": state.validation_report.status if state else "Pending",
    }


@app.get("/api/v1/audit/report/{session_id}")
async def get_audit_report(session_id: str) -> Dict[str, Any]:
    """Exports compiled strategic dossier for a completed session."""
    if session_id not in _SESSION_STATES:
        task_status = _SESSION_TASKS.get(session_id, "Unknown")
        if task_status == "Running":
            raise HTTPException(status_code=202, detail="Audit still in progress")
        raise HTTPException(status_code=404, detail="Audit session report not found")

    state = _SESSION_STATES[session_id]
    return _ORCHESTRATOR.compile_final_strategy_dossier(state)
