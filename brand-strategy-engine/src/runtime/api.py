"""FastAPI REST API runtime for Universal AI Brand Strategy Engine."""

import asyncio
import base64
import binascii
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.agents.base_agent import MASTER_RBAC_POLICY
from src.memory.summarizer import StateSummarizer, TokenBudget
from src.orchestrator.manager import StrategyOrchestrator
from src.orchestrator.state_machine import PipelineStage, StateMachine
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


# ---------------------------------------------------------------------------
# Stage-wise operational UI API (Home Dashboard + Agent tabs)
# State of record is always MasterEngineState in _SESSION_STATES; the browser
# holds only a session_id and re-reads state, so tab switches/reloads are safe.
# ---------------------------------------------------------------------------
UI_DIR = Path(__file__).parent / "ui"
_SESSION_META: Dict[str, Dict[str, Any]] = {}
# Specialist agent instances (and their execution_trace) are shared by the
# orchestrator, so stage runs are serialized to keep per-session traces exact.
_RUN_LOCK = asyncio.Lock()
_ALLOWED_DOC_SUFFIXES = {".pdf", ".docx", ".csv", ".xlsx", ".txt", ".md"}
_MAX_DOC_BYTES = 5 * 1024 * 1024
_MAX_DOCS = 10
_EVIDENCE_DIRS = (Path("/app/evidence_blobs"), Path("evidence_blobs"))


class DocumentUpload(BaseModel):
    filename: str
    content_b64: str


class SessionCreateRequest(BaseModel):
    url: str = Field(..., description="Target brand website URL")
    brand_name: str
    industry: str = "Technology"
    target_market: List[str] = Field(default_factory=lambda: ["Decision Makers"])
    business_goals: List[str] = Field(default_factory=lambda: ["Improve conversion rate"])
    mode: OperationalMode = OperationalMode.MODE_A_PERSONAL
    documents: List[DocumentUpload] = Field(default_factory=list)


def _session(session_id: str) -> tuple:
    state = _SESSION_STATES.get(session_id)
    meta = _SESSION_META.get(session_id)
    if state is None or meta is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state, meta


def _stage_agent(number: int) -> Any:
    if number == 0:
        return _ORCHESTRATOR
    return getattr(_ORCHESTRATOR, f"agent_{number}_{_ORCHESTRATOR.STAGE_SPECS[number][2]}")


def _agent_profile(number: int) -> Dict[str, Any]:
    agent = _stage_agent(number)
    policy = MASTER_RBAC_POLICY[f"Agent_{number}"]
    return {
        "agent_id": f"Agent_{number}",
        "name": agent.name,
        "role": policy["role"],
        "model": agent.model_name,
        "context_window": agent.context_window,
        "tools": list(agent.whitelisted_tool_names),
        "sandbox_permissions": policy["sandbox_permissions"],
        "network_bridge": policy["network_bridge"],
    }


def _write_documents(documents: List[DocumentUpload]) -> Optional[str]:
    if not documents:
        return None
    if len(documents) > _MAX_DOCS:
        raise HTTPException(status_code=413, detail=f"At most {_MAX_DOCS} documents per session")
    docs_dir = Path(tempfile.mkdtemp(prefix="bse_docs_"))
    for doc in documents:
        name = Path(doc.filename).name  # strip any client-supplied path components
        if not name or name.startswith(".") or Path(name).suffix.lower() not in _ALLOWED_DOC_SUFFIXES:
            raise HTTPException(status_code=415, detail=f"Unsupported document type: {name or '<empty>'}")
        try:
            data = base64.b64decode(doc.content_b64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail=f"Invalid base64 content for {name}")
        if len(data) > _MAX_DOC_BYTES:
            raise HTTPException(status_code=413, detail=f"{name} exceeds {_MAX_DOC_BYTES} bytes")
        (docs_dir / name).write_bytes(data)
    return str(docs_dir)


async def _run_stage(session_id: str, number: int) -> Dict[str, Any]:
    state, meta = _session(session_id)
    async with _RUN_LOCK:
        try:
            result = await _ORCHESTRATOR.execute_stage(state, number, tenant_id=meta["tenant_id"])
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    stamp = time.strftime("%H:%M:%S")
    meta["traces"].setdefault(number, []).append({"cycle": result["cycle"], "steps": result["trace"]})
    for ev in result["telemetry"]:
        meta["telemetry"].append({"ts": stamp, "stage": number, "cycle": result["cycle"], **ev})
    return result


async def _run_all_background(session_id: str) -> None:
    state, meta = _SESSION_STATES[session_id], _SESSION_META[session_id]
    meta["running"], meta["error"] = True, None
    try:
        for _ in range(30):  # hard cap: 6 stages + 3 revision loops of (5,6) with headroom
            nxt = _ORCHESTRATOR.next_runnable_stage(state)
            if nxt is None:
                break
            await _run_stage(session_id, nxt)
    except HTTPException as e:
        meta["error"] = str(e.detail)
    except Exception as e:  # surfaced to the UI instead of being swallowed
        meta["error"] = f"{type(e).__name__}: {e}"
    finally:
        meta["running"] = False


def _bucket(init: Any) -> str:
    """Roadmap bucket derived from the initiative's own PriorityMatrix (no new scoring)."""
    effort = init.priority.effort.value
    if effort == "Low":
        return "Quick Wins"
    if effort == "High":
        return "Architectural Bets"
    return "Core Priorities"


async def _build_view(session_id: str) -> Dict[str, Any]:
    from fastapi.encoders import jsonable_encoder

    state, meta = _session(session_id)
    dump = state.model_dump(mode="json", warnings=False)
    nxt = _ORCHESTRATOR.next_runnable_stage(state)
    completed_all = state.current_stage == PipelineStage.COMPLETED.value
    repo = state.research_repository
    stages: List[Dict[str, Any]] = []
    for number, (stage, _, _, slice_fn) in _ORCHESTRATOR.STAGE_SPECS.items():
        if completed_all or (nxt is not None and number < nxt):
            status = "completed"
        elif number == nxt:
            status = "ready"
        else:
            status = "locked"
        gate_reason = None
        if status == "locked":
            gate_reason = f"Waiting for Stage {number - 1} to be completed."
        slice_view = None
        if status in ("ready", "completed"):
            try:
                sl = jsonable_encoder(slice_fn(state))
                slice_view = {"data": sl, "est_tokens": StateSummarizer.estimate_tokens(str(sl))}
            except Exception as e:  # slice preview must never break the dashboard
                slice_view = {"data": {"error": str(e)}, "est_tokens": 0}
        attempts = meta["traces"].get(number, [])
        stages.append({
            "number": number,
            "stage": stage.value,
            "status": status,
            "gate_reason": gate_reason,
            "profile": _agent_profile(number),
            "slice": slice_view,
            "attempts": attempts,
            "digest": StateSummarizer.condense_react_trace(
                [s for a in attempts for s in a["steps"]]
            ),
        })

    approved = [i for i in state.strategic_artifacts.growth_initiatives if i.approval_status.value == "Approved"]
    dossier = None
    if completed_all:
        dossier = _ORCHESTRATOR.compile_strategy_dossier(state)
        if not meta.get("dossier_logged"):
            meta["dossier_logged"] = True
            meta["telemetry"].append({
                "ts": time.strftime("%H:%M:%S"), "stage": 6, "cycle": state.iteration_counter,
                "tool": "compile_strategy_dossier", "detail": f"{len(approved)} approved initiative(s) compiled",
            })
        dossier = jsonable_encoder(dossier)
        dossier["roadmap"] = {
            name: [i.model_dump(mode="json") for i in approved if _bucket(i) == name]
            for name in ("Quick Wins", "Core Priorities", "Architectural Bets")
        }

    ltm = _ORCHESTRATOR.long_term_memory
    baselines = await ltm.get_baselines(meta["tenant_id"])
    dom_rows = []
    for url, snap in repo.dom_snapshots.items():
        m = snap.get("metadata", {}) if isinstance(snap, dict) else {}
        dom_rows.append({
            "url": url,
            "title": m.get("title", ""),
            "headings": len(m.get("headings", [])),
            "preview": str(jsonable_encoder(snap))[:3000],
        })

    return {
        "session_id": session_id,
        "mode": dump["mode"],
        "brand_profile": dump["brand_profile"],
        "current_stage": state.current_stage,
        "iteration_counter": state.iteration_counter,
        "max_revision_loops": StateMachine.MAX_REVISION_LOOPS,
        "next_stage": nxt,
        "running": meta["running"],
        "error": meta["error"],
        "tenant_id": meta["tenant_id"],
        "ingested_chunks": meta["ingested_chunks"],
        "manager": {"profile": _agent_profile(0), "telemetry": meta["telemetry"]},
        "stages": stages,
        "artifacts": dump["strategic_artifacts"],
        "validation_report": dump["validation_report"],
        "repository": {
            "visual_evidence_vnc": dump["research_repository"]["visual_evidence_vnc"],
            "dom_snapshots": dom_rows,
            "rag_citations": dump["research_repository"]["rag_citations"],
            "context_gaps": dump["research_repository"]["context_gaps"],
            "competitor_profiles": dump["research_repository"]["competitor_profiles"],
            "viewports": {"desktop": [1920, 1080], "mobile": [390, 844]},
        },
        "token_budget": {
            "system_reserve": TokenBudget.SYSTEM_RESERVE,
            "stage_input_slice": TokenBudget.STAGE_INPUT_SLICE,
            "active_scratchpad": TokenBudget.ACTIVE_SCRATCHPAD,
            "generation_headroom": TokenBudget.GENERATION_HEADROOM,
            "total_window": TokenBudget.TOTAL_WINDOW,
        },
        "memory": {
            "long_term_backend": "postgresql/pgvector" if ltm.pool else "in-memory fallback (PostgreSQL unavailable)",
            "baselines": jsonable_encoder(baselines),
        },
        "dossier": dossier,
    }


@app.post("/api/v1/session")
async def create_session(request: SessionCreateRequest) -> Dict[str, Any]:
    """Stage 0: initializes BrandProfile + MasterEngineState (optionally ingesting RAG documents)."""
    docs_dir = _write_documents(request.documents)
    profile = BrandProfile(
        website_url=request.url.strip(),
        brand_name=request.brand_name,
        industry=request.industry,
        target_market=request.target_market,
        business_goals=request.business_goals,
    )
    try:
        async with _RUN_LOCK:
            state, tid, chunks = await _ORCHESTRATOR.start_session(profile, request.mode, docs_dir=docs_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _SESSION_STATES[state.session_id] = state
    _SESSION_TASKS[state.session_id] = "Initialized"
    _SESSION_META[state.session_id] = {
        "tenant_id": tid, "ingested_chunks": chunks, "traces": {}, "running": False,
        "error": None, "telemetry": [{
            "ts": time.strftime("%H:%M:%S"), "stage": 0, "cycle": 0, "tool": "start_session",
            "detail": f"Stage 0 complete: {state.mode.value}, {chunks} RAG chunk(s) ingested",
        }],
    }
    return await _build_view(state.session_id)


@app.get("/api/v1/session/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """Canonical MasterEngineState projection for the UI."""
    return await _build_view(session_id)


@app.post("/api/v1/session/{session_id}/stage/{stage_number}")
async def run_session_stage(session_id: str, stage_number: int) -> Dict[str, Any]:
    """Runs one gated stage (1-6). Out-of-order requests are rejected with HTTP 409."""
    _, meta = _session(session_id)
    if meta["running"]:
        raise HTTPException(status_code=409, detail="A full pipeline run is in progress")
    await _run_stage(session_id, stage_number)
    return await _build_view(session_id)


@app.post("/api/v1/session/{session_id}/run-all")
async def run_session_pipeline(session_id: str, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Runs the remaining stages sequentially (Stage 1 -> 6 incl. revision loops) in the background."""
    _, meta = _session(session_id)
    if meta["running"]:
        raise HTTPException(status_code=409, detail="A pipeline run is already in progress")
    meta["running"] = True
    background_tasks.add_task(_run_all_background, session_id)
    return await _build_view(session_id)


@app.get("/api/v1/session/{session_id}/evidence/{evidence_id}/screenshot")
async def get_evidence_screenshot(session_id: str, evidence_id: str) -> FileResponse:
    """Serves a captured VNC frame via the engine bridge (the VNC sandbox itself is never exposed)."""
    state, _ = _session(session_id)
    for ev in state.research_repository.visual_evidence_vnc:
        if ev.evidence_id == evidence_id and ev.screenshot_uri:
            path = Path(ev.screenshot_uri).resolve()
            allowed = any(d.resolve() in path.parents for d in _EVIDENCE_DIRS)
            if allowed and path.suffix == ".png" and path.is_file():
                return FileResponse(path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Screenshot not available")


@app.get("/", include_in_schema=False)
@app.get("/ui", include_in_schema=False)
async def serve_ui() -> FileResponse:
    index = UI_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="UI bundle missing")
    return FileResponse(index, media_type="text/html")

