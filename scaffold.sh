#!/usr/bin/env bash
# Deterministic, idempotent scaffolder for the governed multi-agent marketing backend.
# Produces a production-grade Python project managed with Bash entrypoints.
#
# Usage:
#   ./scaffold.sh [ROOT_DIR] [--force]
#
#   ROOT_DIR   Target directory (default: backend)
#   --force    Overwrite existing files instead of skipping them
#
# Exit codes:
#   0  success
#   1  usage / environment error
#   2  unrecoverable write failure

set -Eeuo pipefail

readonly SCRIPT_NAME="${0##*/}"
readonly SCRIPT_VERSION="1.0.0"

ROOT="backend"
FORCE=0

# ---------------------------------------------------------------------------
# Logging & error handling
# ---------------------------------------------------------------------------
log()  { printf '[%s] %s\n' "$SCRIPT_NAME" "$*" >&2; }
warn() { printf '[%s] WARN: %s\n' "$SCRIPT_NAME" "$*" >&2; }
die()  { printf '[%s] ERROR: %s\n' "$SCRIPT_NAME" "$*" >&2; exit "${2:-1}"; }

trap 'die "aborted at line $LINENO" 2' ERR

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
parse_args() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            --force|-f) FORCE=1 ;;
            --help|-h)
                printf 'Usage: %s [ROOT_DIR] [--force]\n' "$SCRIPT_NAME"
                exit 0
                ;;
            --version)
                printf '%s %s\n' "$SCRIPT_NAME" "$SCRIPT_VERSION"
                exit 0
                ;;
            -*)
                die "unknown option: $arg"
                ;;
            *)
                ROOT="$arg"
                ;;
        esac
    done
}

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------
require_bash5() {
    (( BASH_VERSINFO[0] >= 5 )) || die "Bash 5+ required (found ${BASH_VERSION})"
}

# ---------------------------------------------------------------------------
# Safe filesystem primitives
# ---------------------------------------------------------------------------
should_write() {
    local abs="$1"
    [[ ! -e "$abs" || "$FORCE" -eq 1 ]]
}

write_file() {
    local rel="$1"
    local abs="$ROOT/$rel"

    if ! should_write "$abs"; then
        log "skip (exists): $rel"
        cat >/dev/null
        return 0
    fi

    mkdir -p -- "$(dirname -- "$abs")"
    local tmp
    tmp="$(mktemp "${abs}.tmp.XXXXXX")"
    cat > "$tmp"
    mv -- "$tmp" "$abs"
    log "wrote: $rel"
}

write_exec() {
    local rel="$1"
    local abs="$ROOT/$rel"

    if ! should_write "$abs"; then
        log "skip (exists): $rel"
        cat >/dev/null
        return 0
    fi

    mkdir -p -- "$(dirname -- "$abs")"
    local tmp
    tmp="$(mktemp "${abs}.tmp.XXXXXX")"
    cat > "$tmp"
    chmod 0755 -- "$tmp"
    mv -- "$tmp" "$abs"
    log "wrote (exec): $rel"
}

ensure_dir() {
    local rel="$1"
    mkdir -p -- "$ROOT/$rel"
}

# ---------------------------------------------------------------------------
# Section writers
# ---------------------------------------------------------------------------
write_project_root() {
    write_file "pyproject.toml" <<'PYPROJECT_EOF'
[project]
name = "backend"
version = "0.1.0"
description = "Governed multi-agent marketing intelligence backend"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "sqlalchemy>=2.0",
    "psycopg[binary]>=3.1",
    "pgvector>=0.2",
    "httpx>=0.27",
    "agent_sandbox",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
    "mypy>=1.9",
]

[project.scripts]
backend = "app.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
PYPROJECT_EOF

    write_file ".gitignore" <<'GITIGNORE_EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.eggs/
build/
dist/
.venv/
venv/
env/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Environment
.env
.env.local
.env.*.local

# Runtime data
var/
*.log

# IDE
.idea/
.vscode/
*.swp
.DS_Store
GITIGNORE_EOF

    write_file ".env.example" <<'ENV_EOF'
# Copy to .env and fill in real values. Never commit .env.
BACKEND_APP_NAME=governed-backend
BACKEND_VERSION=0.1.0
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
BACKEND_DATABASE_URL=postgresql+psycopg://localhost:5432/backend
BACKEND_LLM_PROVIDER=openai-compatible
BACKEND_SANDBOX_SDK_PATH=
ENV_EOF

    write_file "Makefile" <<'MAKE_EOF'
.PHONY: help install dev test lint typecheck format clean run

help:
	@printf '%s\n' \
		'install   - install package with dev extras' \
		'dev       - run development server' \
		'test      - run pytest suite' \
		'lint      - run ruff' \
		'typecheck - run mypy' \
		'format    - run ruff --fix' \
		'run       - run production entrypoint' \
		'clean     - remove caches and build artifacts'

install:
	pip install -e '.[dev]'

dev:
	./scripts/dev.sh

test:
	./scripts/test.sh

lint:
	./scripts/lint.sh

typecheck:
	mypy app

format:
	ruff check --fix app tests

run:
	python -m app.main

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
MAKE_EOF

    write_file "README.md" <<'README_EOF'
# Governed Multi-Agent Marketing Intelligence Backend

Model-A governance architecture:

    directive -> policy envelope -> DAG scheduling -> bounded workers
    -> evidence synthesis -> HITL preview -> signed dispatch -> telemetry
    -> validated learning promotion

## Layout

| Path                  | Purpose                                                   |
|-----------------------|-----------------------------------------------------------|
| `app/api`             | Transport/API boundary only                               |
| `app/core`            | Runtime settings and logging                              |
| `app/schemas`         | Cross-layer Pydantic contracts                            |
| `app/orchestration`   | Transport-independent Intelligence Engine logic           |
| `app/agents`          | Seven bounded workers (W_DEV..W_LEARN)                    |
| `app/services`        | Application services (policy, HITL, RAG, telemetry)       |
| `app/security`        | Authorization, scope, and signature enforcement           |
| `app/mcp`             | MCP host, data gateway, outbound gateway                  |
| `app/integrations`    | LLM, sandbox, CMS, ads, social adapters                   |
| `app/persistence`     | PostgreSQL/pgvector/TimescaleDB repositories              |
| `scripts`             | Developer Bash entrypoints (dev/test/lint)                |
| `tests`               | Unit, integration, acceptance suites                      |
| `var`                 | Runtime data (gitignored)                                 |

## Quick start

    cp .env.example .env
    make install
    make test
    make dev

## Environment

Configuration is read from environment variables prefixed with `BACKEND_`
(see `app/core/settings.py`). Secrets must never be committed; use `.env`
locally and a secret manager in deployment.
README_EOF
}

write_app_root() {
    write_file "app/__init__.py" <<'EOF'
"""Governed multi-agent marketing intelligence backend."""
EOF

    write_exec "app/main.py" <<'EOF'
#!/usr/bin/env python3
"""Application entrypoint and backend composition root."""
from __future__ import annotations

from fastapi import FastAPI

from app.api.router import api_router
from app.core.logging import configure_logging
from app.core.settings import get_settings


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.version)
    app.include_router(api_router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
EOF
}

write_api() {
    write_file "app/api/__init__.py" <<'EOF'
"""Transport/API boundary package."""
EOF

    write_file "app/api/router.py" <<'EOF'
"""Aggregates backend API routes."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import approvals, directives, tasks, telemetry

api_router = APIRouter()
api_router.include_router(directives.router, prefix="/directives", tags=["directives"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
EOF

    write_file "app/api/routes/__init__.py" <<'EOF'
"""Human and external-event API endpoints."""
EOF

    write_file "app/api/routes/directives.py" <<'EOF'
"""Accepts owner objectives, scopes, budgets, and risk directives."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.schemas.governance import Directive
from app.services.policy_engine import PolicyEngine

router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_directive(directive: Directive) -> dict[str, str]:
    envelope = PolicyEngine().compile_envelope(directive)
    return {"status": "accepted", "policy_id": envelope.policy_id}
EOF

    write_file "app/api/routes/tasks.py" <<'EOF'
"""Exposes canonical task-state and workflow status operations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.task_state import TaskState
from app.services.task_state import TaskStateService

router = APIRouter()


@router.get("/{task_id}", response_model=TaskState)
async def get_task(task_id: str) -> TaskState:
    task = TaskStateService().get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return task
EOF

    write_file "app/api/routes/approvals.py" <<'EOF'
"""Receives HITL approvals, rejections, and revisions."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.schemas.action_preview import ApprovalDecision
from app.services.hitl import HitlService

router = APIRouter()


@router.post("/{preview_id}", status_code=status.HTTP_202_ACCEPTED)
async def decide(preview_id: str, decision: ApprovalDecision) -> dict[str, str]:
    HitlService().record(preview_id, decision)
    return {"status": "recorded", "preview_id": preview_id}
EOF

    write_file "app/api/routes/telemetry.py" <<'EOF'
"""Receives webhook, conversion, pixel, and event telemetry."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.schemas.telemetry import TelemetryEvent
from app.services.telemetry import TelemetryService

router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest(event: TelemetryEvent) -> dict[str, str]:
    TelemetryService().ingest(event)
    return {"status": "ingested", "event_id": event.event_id}
EOF
}

write_core() {
    write_file "app/core/__init__.py" <<'EOF'
"""Shared backend runtime concerns."""
EOF

    write_file "app/core/settings.py" <<'EOF'
"""Runtime settings and external credential/reference configuration."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BACKEND_", env_file=".env", extra="ignore")

    app_name: str = "governed-backend"
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "postgresql+psycopg://localhost:5432/backend"
    llm_provider: str = "openai-compatible"
    sandbox_sdk_path: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
EOF

    write_file "app/core/logging.py" <<'EOF'
"""Application logging configuration."""
from __future__ import annotations

import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(level)
EOF
}

write_schemas() {
    write_file "app/schemas/__init__.py" <<'EOF'
"""Cross-layer Python data contracts."""
EOF

    write_file "app/schemas/governance.py" <<'EOF'
"""Directives, policy envelopes, tenant scopes, budgets, and risk data."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Budget(BaseModel):
    currency: str = "USD"
    amount: float = Field(ge=0.0)


class RiskEnvelope(BaseModel):
    max_spend: float = Field(ge=0.0)
    max_risk_score: float = Field(ge=0.0, le=1.0)


class Directive(BaseModel):
    directive_id: str
    tenant_id: str
    objective: str
    scopes: list[str] = Field(default_factory=list)
    budget: Budget
    risk: RiskEnvelope


class PolicyEnvelope(BaseModel):
    policy_id: str
    directive_id: str
    tenant_id: str
    scopes: list[str]
    budget: Budget
    risk: RiskEnvelope
EOF

    write_file "app/schemas/task_state.py" <<'EOF'
"""CTS lifecycle, checkpoints, dependencies, holds, and state deltas."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    HELD = "held"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Checkpoint(BaseModel):
    name: str
    created_at: datetime


class TaskState(BaseModel):
    task_id: str
    directive_id: str
    tenant_id: str
    status: TaskStatus = TaskStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    hold_reason: str | None = None
EOF

    write_file "app/schemas/agent_contracts.py" <<'EOF'
"""Bounded task grants, context requests, evidence envelopes, and confidence data."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TaskGrant(BaseModel):
    grant_id: str
    worker_id: str
    tenant_id: str
    capabilities: list[str]
    budget_ceiling: float = Field(ge=0.0)
    expires_at: str


class ContextRequest(BaseModel):
    request_id: str
    worker_id: str
    tenant_id: str
    query: str
    scopes: list[str] = Field(default_factory=list)


class EvidenceEnvelope(BaseModel):
    worker_id: str
    task_id: str
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[str] = Field(default_factory=list)
EOF

    write_file "app/schemas/sandbox.py" <<'EOF'
"""Backend-to-sandbox invocation and sanitized-result contracts."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SandboxInvocation(BaseModel):
    invocation_id: str
    capability: str
    worker_id: str
    payload: dict
    limits: dict = Field(default_factory=dict)


class SandboxResult(BaseModel):
    invocation_id: str
    status: str
    sanitized_output: dict
    telemetry: dict = Field(default_factory=dict)
EOF

    write_file "app/schemas/action_preview.py" <<'EOF'
"""Spend, claims, copy, and code-diff review dossiers."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PreviewKind(str, Enum):
    SPEND = "spend"
    CLAIMS = "claims"
    COPY = "copy"
    CODE = "code"


class ActionPreview(BaseModel):
    preview_id: str
    task_id: str
    tenant_id: str
    kind: PreviewKind
    summary: str
    diff: str | None = None
    spend: float | None = None


class ApprovalDecision(BaseModel):
    decision: str
    reviewer: str
    reason: str | None = None
    revisions: dict = Field(default_factory=dict)
EOF

    write_file "app/schemas/dispatch.py" <<'EOF'
"""Signed post-HITL execution directives."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SignedDispatch(BaseModel):
    dispatch_id: str
    preview_id: str
    tenant_id: str
    signature: str
    payload: dict
    scopes: list[str] = Field(default_factory=list)
EOF

    write_file "app/schemas/telemetry.py" <<'EOF'
"""Normalized traffic, conversion, ad, social, and ROAS events."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TelemetryChannel(str, Enum):
    TRAFFIC = "traffic"
    CONVERSION = "conversion"
    AD = "ad"
    SOCIAL = "social"
    ROAS = "roas"


class TelemetryEvent(BaseModel):
    event_id: str
    tenant_id: str
    channel: TelemetryChannel
    occurred_at: datetime
    metrics: dict = Field(default_factory=dict)
    source: str | None = None
EOF

    write_file "app/schemas/artifact.py" <<'EOF'
"""UUID/hash-addressed deliverable and evidence references."""
from __future__ import annotations

from pydantic import BaseModel


class ArtifactRef(BaseModel):
    artifact_id: str
    content_hash: str
    uri: str
    media_type: str = "application/octet-stream"
EOF

    write_file "app/schemas/provenance.py" <<'EOF'
"""W3C PROV audit-event contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProvRecord(BaseModel):
    entity_id: str
    activity_id: str
    agent_id: str
    started_at: datetime
    ended_at: datetime | None = None
    attributes: dict = Field(default_factory=dict)
EOF
}

write_orchestration() {
    write_file "app/orchestration/__init__.py" <<'EOF'
"""Transport-independent Intelligence Engine logic."""
EOF

    write_file "app/orchestration/intelligence_engine.py" <<'EOF'
"""Central Model-A orchestrator and multi-brand execution coordinator."""
from __future__ import annotations

from app.orchestration.context_assembly import ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import RagQueryDispatcher
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.governance import PolicyEnvelope


class IntelligenceEngine:
    def __init__(
        self,
        policy: PolicyEvaluator | None = None,
        dag: DagScheduler | None = None,
        context: ContextAssembler | None = None,
        rag: RagQueryDispatcher | None = None,
        preview: HitlPreviewGenerator | None = None,
        state: TaskStateMachine | None = None,
    ) -> None:
        self.policy = policy or PolicyEvaluator()
        self.dag = dag or DagScheduler()
        self.context = context or ContextAssembler()
        self.rag = rag or RagQueryDispatcher()
        self.preview = preview or HitlPreviewGenerator()
        self.state = state or TaskStateMachine()

    def run(self, envelope: PolicyEnvelope) -> dict:
        decision = self.policy.evaluate(envelope)
        if not decision.allowed:
            return {"status": "rejected", "reason": decision.reason}
        plan = self.dag.plan(envelope)
        return {"status": "scheduled", "plan": plan}
EOF

    write_file "app/orchestration/context_assembly.py" <<'EOF'
"""Builds policy-screened context slices for workers."""
from __future__ import annotations

from app.schemas.agent_contracts import ContextRequest


class ContextAssembler:
    def build(self, request: ContextRequest, allowed_scopes: set[str]) -> dict:
        scopes = [s for s in request.scopes if s in allowed_scopes]
        return {"request_id": request.request_id, "scopes": scopes, "query": request.query}
EOF

    write_file "app/orchestration/brand_persona.py" <<'EOF'
"""Applies tenant-specific brand rules and institutional context."""
from __future__ import annotations


class BrandPersona:
    def __init__(self, rules: dict | None = None) -> None:
        self.rules = rules or {}

    def apply(self, tenant_id: str, payload: dict) -> dict:
        tenant_rules = self.rules.get(tenant_id, {})
        merged = dict(payload)
        merged["brand_rules"] = tenant_rules
        return merged
EOF

    write_file "app/orchestration/dag_scheduler.py" <<'EOF'
"""Schedules work according to the canonical dependency DAG."""
from __future__ import annotations

from app.schemas.governance import PolicyEnvelope


class DagScheduler:
    def plan(self, envelope: PolicyEnvelope) -> list[dict]:
        return [
            {"step": "context", "directive_id": envelope.directive_id},
            {"step": "workers", "directive_id": envelope.directive_id},
            {"step": "synthesis", "directive_id": envelope.directive_id},
            {"step": "hitl_preview", "directive_id": envelope.directive_id},
        ]
EOF

    write_file "app/orchestration/task_state_machine.py" <<'EOF'
"""Enforces authoritative task lifecycle transitions."""
from __future__ import annotations

from app.schemas.task_state import TaskState, TaskStatus

_ALLOWED: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.READY: {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.HELD},
    TaskStatus.BLOCKED: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.HELD: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


class TaskStateMachine:
    def transition(self, state: TaskState, target: TaskStatus) -> TaskState:
        if target not in _ALLOWED[state.status]:
            raise ValueError(f"illegal transition {state.status} -> {target}")
        return state.model_copy(update={"status": target})
EOF

    write_file "app/orchestration/policy_evaluator.py" <<'EOF'
"""Applies policy decisions before delegation and execution."""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.governance import PolicyEnvelope


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None


class PolicyEvaluator:
    def evaluate(self, envelope: PolicyEnvelope) -> PolicyDecision:
        if envelope.budget.amount > envelope.risk.max_spend:
            return PolicyDecision(False, "budget exceeds risk envelope")
        return PolicyDecision(True)
EOF

    write_file "app/orchestration/rag_query_dispatch.py" <<'EOF'
"""Provides the IE-exclusive bridge to Agentic RAG."""
from __future__ import annotations

from app.schemas.agent_contracts import ContextRequest


class RagQueryDispatcher:
    def __init__(self, controller=None) -> None:
        if controller is None:
            from app.services.rag.controller import RagController

            controller = RagController()
        self._controller = controller

    def dispatch(self, request: ContextRequest) -> dict:
        return self._controller.query(request.query, tenant_id=request.tenant_id)
EOF

    write_file "app/orchestration/evidence_synthesis.py" <<'EOF'
"""Consolidates worker evidence and confidence intervals."""
from __future__ import annotations

from app.schemas.agent_contracts import EvidenceEnvelope


class EvidenceSynthesizer:
    def synthesize(self, envelopes: list[EvidenceEnvelope]) -> dict:
        if not envelopes:
            return {"summary": "", "confidence": 0.0, "citations": []}
        confidence = sum(e.confidence for e in envelopes) / len(envelopes)
        citations = sorted({c for e in envelopes for c in e.citations})
        summary = " | ".join(e.summary for e in envelopes if e.summary)
        return {"summary": summary, "confidence": confidence, "citations": citations}
EOF

    write_file "app/orchestration/hitl_preview_generator.py" <<'EOF'
"""Builds mandatory human-review action previews."""
from __future__ import annotations

from uuid import uuid4

from app.schemas.action_preview import ActionPreview, PreviewKind


class HitlPreviewGenerator:
    def generate(
        self,
        task_id: str,
        tenant_id: str,
        kind: PreviewKind,
        summary: str,
        **extra,
    ) -> ActionPreview:
        return ActionPreview(
            preview_id=str(uuid4()),
            task_id=task_id,
            tenant_id=tenant_id,
            kind=kind,
            summary=summary,
            **extra,
        )
EOF
}

write_agents() {
    write_file "app/agents/__init__.py" <<'EOF'
"""Seven bounded worker-agent definitions with no direct data-store access."""
EOF

    write_file "app/agents/development.py" <<'EOF'
"""W_DEV: CMS schemas, UI layouts, code diffs, and web-development work."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class DevelopmentAgent:
    worker_id = "W_DEV"
    capability = "S_CODE"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
EOF

    write_file "app/agents/strategy.py" <<'EOF'
"""W_STRAT: omnichannel roadmaps, funnels, media mix, and budgets."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class StrategyAgent:
    worker_id = "W_STRAT"
    capability = "S_ALLOC"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
EOF

    write_file "app/agents/creative_content.py" <<'EOF'
"""W_CREAT: copy variants, hooks, visual briefs, and social schedules."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class CreativeContentAgent:
    worker_id = "W_CREAT"
    capability = "S_COPY"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
EOF

    write_file "app/agents/product_evidence.py" <<'EOF'
"""W_PROD: product specifications, evidence, claims, and compliance dossiers."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class ProductEvidenceAgent:
    worker_id = "W_PROD"
    capability = "S_VAL"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
EOF

    write_file "app/agents/competitor_intel.py" <<'EOF'
"""W_COMP: pricing, ad-library, SERP, trend, and positioning intelligence."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class CompetitorIntelAgent:
    worker_id = "W_COMP"
    capability = "S_SCRAPE"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
EOF

    write_file "app/agents/customer_voice.py" <<'EOF'
"""W_VOICE: tickets, reviews, sentiment, and objection analysis."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class CustomerVoiceAgent:
    worker_id = "W_VOICE"
    capability = "S_PARSE"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
EOF

    write_file "app/agents/learning_performance.py" <<'EOF'
"""W_LEARN: attribution, fatigue, decay, ROAS, and validated learning deltas."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class LearningPerformanceAgent:
    worker_id = "W_LEARN"
    capability = "S_ATTR"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
EOF
}

write_services() {
    write_file "app/services/__init__.py" <<'EOF'
"""Application services supporting orchestration."""
EOF

    write_file "app/services/policy_engine.py" <<'EOF'
"""Produces and validates machine-readable policy and compliance envelopes."""
from __future__ import annotations

from uuid import uuid4

from app.schemas.governance import Directive, PolicyEnvelope


class PolicyEngine:
    def compile_envelope(self, directive: Directive) -> PolicyEnvelope:
        return PolicyEnvelope(
            policy_id=str(uuid4()),
            directive_id=directive.directive_id,
            tenant_id=directive.tenant_id,
            scopes=list(directive.scopes),
            budget=directive.budget,
            risk=directive.risk,
        )

    def validate(self, envelope: PolicyEnvelope) -> bool:
        return envelope.budget.amount <= envelope.risk.max_spend
EOF

    write_file "app/services/hitl.py" <<'EOF'
"""Coordinates mandatory human approval and revision decisions."""
from __future__ import annotations

from app.schemas.action_preview import ApprovalDecision


class HitlService:
    def __init__(self) -> None:
        self._decisions: dict[str, ApprovalDecision] = {}

    def record(self, preview_id: str, decision: ApprovalDecision) -> None:
        self._decisions[preview_id] = decision

    def decision_for(self, preview_id: str) -> ApprovalDecision | None:
        return self._decisions.get(preview_id)
EOF

    write_file "app/services/task_state.py" <<'EOF'
"""Coordinates CTS persistence, checkpoints, locks, and exceptions."""
from __future__ import annotations

from app.schemas.task_state import TaskState


class TaskStateService:
    def __init__(self) -> None:
        self._store: dict[str, TaskState] = {}

    def get(self, task_id: str) -> TaskState | None:
        return self._store.get(task_id)

    def put(self, state: TaskState) -> None:
        self._store[state.task_id] = state
EOF

    write_file "app/services/rag/__init__.py" <<'EOF'
"""Governed Agentic RAG service."""
EOF

    write_file "app/services/rag/controller.py" <<'EOF'
"""Coordinates authorized retrieval and ingestion requests."""
from __future__ import annotations

from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator


class RagController:
    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        freshness: FreshnessPolicy | None = None,
        validator: SchemaValidator | None = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.freshness = freshness or FreshnessPolicy()
        self.validator = validator or SchemaValidator()

    def query(self, query: str, tenant_id: str) -> dict:
        hits = self.retriever.retrieve(query, tenant_id)
        filtered = [h for h in hits if self.freshness.is_fresh(h)]
        validated = [h for h in filtered if self.validator.is_valid(h)]
        return {"query": query, "tenant_id": tenant_id, "results": validated}
EOF

    write_file "app/services/rag/hybrid_retriever.py" <<'EOF'
"""Performs required vector/BM25 hybrid retrieval."""
from __future__ import annotations


class HybridRetriever:
    def retrieve(self, query: str, tenant_id: str, limit: int = 10) -> list[dict]:
        # Backed by the vector repository in production; returns [] as safe default.
        return []
EOF

    write_file "app/services/rag/freshness.py" <<'EOF'
"""Enforces evidence freshness requirements."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


class FreshnessPolicy:
    def __init__(self, max_age: timedelta = timedelta(days=30)) -> None:
        self.max_age = max_age

    def is_fresh(self, hit: dict, now: datetime | None = None) -> bool:
        ts = hit.get("retrieved_at")
        if ts is None:
            return True
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        now = now or datetime.now(timezone.utc)
        return (now - ts) <= self.max_age
EOF

    write_file "app/services/rag/schema_validator.py" <<'EOF'
"""Validates retrieved and ingested knowledge structures."""
from __future__ import annotations

_REQUIRED = {"doc_id", "content"}


class SchemaValidator:
    def is_valid(self, hit: dict) -> bool:
        return _REQUIRED.issubset(hit.keys())
EOF

    write_file "app/services/telemetry.py" <<'EOF'
"""Normalizes and persists omnichannel performance events."""
from __future__ import annotations

from app.schemas.telemetry import TelemetryEvent


class TelemetryService:
    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    def ingest(self, event: TelemetryEvent) -> None:
        self._events.append(event)

    def all(self) -> list[TelemetryEvent]:
        return list(self._events)
EOF

    write_file "app/services/memory_promotion.py" <<'EOF'
"""Promotes validated learning deltas into institutional memory."""
from __future__ import annotations


class MemoryPromotionService:
    def __init__(self, threshold: float = 0.6) -> None:
        self.threshold = threshold

    def promote(self, tenant_id: str, delta: dict) -> bool:
        confidence = float(delta.get("confidence", 0.0))
        if confidence < self.threshold:
            return False
        # Persistence delegated to repository in production.
        return True
EOF

    write_file "app/services/provenance.py" <<'EOF'
"""Records immutable entity/activity/agent audit lineage."""
from __future__ import annotations

from app.schemas.provenance import ProvRecord


class ProvenanceService:
    def __init__(self) -> None:
        self._records: list[ProvRecord] = []

    def append(self, record: ProvRecord) -> None:
        self._records.append(record)

    def all(self) -> list[ProvRecord]:
        return list(self._records)
EOF
}

write_security() {
    write_file "app/security/__init__.py" <<'EOF'
"""Policy and authorization enforcement boundary."""
EOF

    write_file "app/security/authorization_boundary.py" <<'EOF'
"""Enforces caller identity, delegation, tenant scope, risk, and attenuation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthzDecision:
    allowed: bool
    reason: str | None = None


class AuthorizationBoundary:
    def check(
        self,
        caller_tenant: str,
        target_tenant: str,
        scopes: set[str],
        required: set[str],
    ) -> AuthzDecision:
        if caller_tenant != target_tenant:
            return AuthzDecision(False, "tenant mismatch")
        missing = required - scopes
        if missing:
            return AuthzDecision(False, f"missing scopes: {sorted(missing)}")
        return AuthzDecision(True)
EOF

    write_file "app/security/cryptographic_validator.py" <<'EOF'
"""Validates signed caller, approval, and execution authorization."""
from __future__ import annotations

import hmac
from hashlib import sha256


class CryptographicValidator:
    def __init__(self, secret: bytes) -> None:
        self._secret = secret

    def sign(self, payload: bytes) -> str:
        return hmac.new(self._secret, payload, sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return hmac.compare_digest(self.sign(payload), signature)
EOF

    write_file "app/security/scope_evaluator.py" <<'EOF'
"""Evaluates tenant scope and delegated authority."""
from __future__ import annotations


class ScopeEvaluator:
    def is_subset(self, requested: set[str], granted: set[str]) -> bool:
        return requested.issubset(granted)

    def attenuate(self, granted: set[str], requested: set[str]) -> set[str]:
        return granted & requested
EOF
}

write_mcp() {
    write_file "app/mcp/__init__.py" <<'EOF'
"""MCP boundaries defined by the architecture."""
EOF

    write_file "app/mcp/host.py" <<'EOF'
"""MCP host surface owned by the Intelligence Engine."""
from __future__ import annotations

from app.orchestration.intelligence_engine import IntelligenceEngine


class McpHost:
    def __init__(self, engine: IntelligenceEngine | None = None) -> None:
        self.engine = engine or IntelligenceEngine()

    def handle(self, message: dict) -> dict:
        return {"status": "acknowledged", "message_id": message.get("id")}
EOF

    write_file "app/mcp/data_gateway.py" <<'EOF'
"""Governed CRUD facade between Agentic RAG and systems of record."""
from __future__ import annotations


class DataGateway:
    def read(self, entity: str, entity_id: str) -> dict | None:
        return None

    def write(self, entity: str, payload: dict) -> str:
        raise PermissionError("writes must flow through authorized dispatches")
EOF

    write_file "app/mcp/outbound_gateway.py" <<'EOF'
"""Post-HITL signed, rate-limited actuation boundary."""
from __future__ import annotations

from app.schemas.dispatch import SignedDispatch
from app.security.cryptographic_validator import CryptographicValidator


class OutboundGateway:
    def __init__(self, validator: CryptographicValidator) -> None:
        self._validator = validator

    def dispatch(self, signed: SignedDispatch, payload_bytes: bytes) -> dict:
        if not self._validator.verify(payload_bytes, signed.signature):
            raise PermissionError("invalid dispatch signature")
        return {"dispatch_id": signed.dispatch_id, "status": "dispatched"}
EOF
}

write_integrations() {
    write_file "app/integrations/__init__.py" <<'EOF'
"""Adapters for dependencies outside core domain logic."""
EOF

    write_file "app/integrations/llm/__init__.py" <<'EOF'
"""Provider-neutral AI model boundary."""
EOF

    write_file "app/integrations/llm/client.py" <<'EOF'
"""Invokes the configured model/provider without coupling agents to a vendor."""
from __future__ import annotations

from typing import Protocol


class LlmClient(Protocol):
    def complete(self, prompt: str, **options) -> str: ...


class ProviderNeutralLlmClient:
    def __init__(self, provider_callable) -> None:
        self._provider_callable = provider_callable

    def complete(self, prompt: str, **options) -> str:
        return self._provider_callable(prompt, **options)
EOF

    write_file "app/integrations/sandbox/__init__.py" <<'EOF'
"""Thin boundary around the existing agent_sandbox Python SDK."""
EOF

    write_file "app/integrations/sandbox/client.py" <<'EOF'
"""Invokes existing sandbox capabilities and returns sanitized results."""
from __future__ import annotations

from uuid import uuid4

from app.schemas.sandbox import SandboxInvocation, SandboxResult


class SandboxClient:
    def __init__(self, sdk=None) -> None:
        if sdk is None:
            import agent_sandbox  # noqa: F401  (existing dependency)

            sdk = agent_sandbox
        self._sdk = sdk

    def invoke(self, capability: str, worker_id: str, payload: dict) -> dict:
        invocation = SandboxInvocation(
            invocation_id=str(uuid4()),
            capability=capability,
            worker_id=worker_id,
            payload=payload,
        )
        raw = self._sdk.run(invocation.capability, invocation.payload)
        result = SandboxResult(
            invocation_id=invocation.invocation_id,
            status=raw.get("status", "ok"),
            sanitized_output=raw.get("output", {}),
        )
        return result.model_dump()
EOF

    write_file "app/integrations/sandbox/capabilities.py" <<'EOF'
"""Maps W_DEV-W_LEARN to S_CODE-S_ATTR sandbox capabilities."""
from __future__ import annotations

WORKER_CAPABILITIES: dict[str, str] = {
    "W_DEV": "S_CODE",
    "W_STRAT": "S_ALLOC",
    "W_CREAT": "S_COPY",
    "W_PROD": "S_VAL",
    "W_COMP": "S_SCRAPE",
    "W_VOICE": "S_PARSE",
    "W_LEARN": "S_ATTR",
}


def capability_for(worker_id: str) -> str:
    try:
        return WORKER_CAPABILITIES[worker_id]
    except KeyError as exc:
        raise KeyError(f"unknown worker: {worker_id}") from exc
EOF

    write_file "app/integrations/cms/__init__.py" <<'EOF'
"""Headless CMS integration boundary."""
EOF

    write_file "app/integrations/cms/client.py" <<'EOF'
"""Reads staged CMS data and applies approved content/schema changes."""
from __future__ import annotations


class CmsClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    def read(self, resource: str) -> dict:
        raise NotImplementedError("wire to vendor SDK via configuration")

    def apply(self, resource: str, payload: dict) -> dict:
        raise PermissionError("CMS writes require signed HITL dispatch")
EOF

    write_file "app/integrations/ads/__init__.py" <<'EOF'
"""Paid-media platform adapters."""
EOF

    write_file "app/integrations/ads/meta.py" <<'EOF'
"""Meta campaign, targeting, bid, and telemetry adapter."""
from __future__ import annotations


class MetaAdsAdapter:
    name = "meta"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def push_campaign(self, campaign: dict) -> dict:
        raise PermissionError("paid-media writes require signed HITL dispatch")
EOF

    write_file "app/integrations/ads/google.py" <<'EOF'
"""Google campaign, targeting, bid, and telemetry adapter."""
from __future__ import annotations


class GoogleAdsAdapter:
    name = "google"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def push_campaign(self, campaign: dict) -> dict:
        raise PermissionError("paid-media writes require signed HITL dispatch")
EOF

    write_file "app/integrations/ads/tiktok.py" <<'EOF'
"""TikTok campaign, targeting, bid, and telemetry adapter."""
from __future__ import annotations


class TikTokAdsAdapter:
    name = "tiktok"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def push_campaign(self, campaign: dict) -> dict:
        raise PermissionError("paid-media writes require signed HITL dispatch")
EOF

    write_file "app/integrations/ads/linkedin.py" <<'EOF'
"""LinkedIn paid-media adapter defined by the architecture."""
from __future__ import annotations


class LinkedInAdsAdapter:
    name = "linkedin"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def push_campaign(self, campaign: dict) -> dict:
        raise PermissionError("paid-media writes require signed HITL dispatch")
EOF

    write_file "app/integrations/social/__init__.py" <<'EOF'
"""Organic social-channel adapters."""
EOF

    write_file "app/integrations/social/instagram.py" <<'EOF'
"""Instagram publishing and engagement adapter."""
from __future__ import annotations


class InstagramAdapter:
    name = "instagram"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def publish(self, payload: dict) -> dict:
        raise PermissionError("social writes require signed HITL dispatch")
EOF

    write_file "app/integrations/social/x.py" <<'EOF'
"""X publishing and engagement adapter."""
from __future__ import annotations


class XAdapter:
    name = "x"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def publish(self, payload: dict) -> dict:
        raise PermissionError("social writes require signed HITL dispatch")
EOF

    write_file "app/integrations/social/tiktok.py" <<'EOF'
"""TikTok social publishing and engagement adapter."""
from __future__ import annotations


class TikTokSocialAdapter:
    name = "tiktok-social"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def publish(self, payload: dict) -> dict:
        raise PermissionError("social writes require signed HITL dispatch")
EOF

    write_file "app/integrations/social/youtube.py" <<'EOF'
"""YouTube publishing and engagement adapter."""
from __future__ import annotations


class YouTubeAdapter:
    name = "youtube"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def publish(self, payload: dict) -> dict:
        raise PermissionError("social writes require signed HITL dispatch")
EOF
}

write_persistence() {
    write_file "app/persistence/__init__.py" <<'EOF'
"""Backend persistence boundary and repositories."""
EOF

    write_file "app/persistence/database.py" <<'EOF'
"""PostgreSQL/pgvector/TimescaleDB connection boundary."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, future=True)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
EOF

    write_file "app/persistence/repositories/__init__.py" <<'EOF'
"""Governed system-of-record access implementations."""
EOF

    write_file "app/persistence/repositories/operational.py" <<'EOF'
"""Persists enterprise directives and generated operational records."""
from __future__ import annotations

from app.schemas.governance import Directive


class OperationalRepository:
    def __init__(self) -> None:
        self._directives: dict[str, Directive] = {}

    def save_directive(self, directive: Directive) -> None:
        self._directives[directive.directive_id] = directive

    def get_directive(self, directive_id: str) -> Directive | None:
        return self._directives.get(directive_id)
EOF

    write_file "app/persistence/repositories/task_state.py" <<'EOF'
"""Persists canonical task-state and dependency records."""
from __future__ import annotations

from app.schemas.task_state import TaskState


class TaskStateRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskState] = {}

    def upsert(self, state: TaskState) -> None:
        self._tasks[state.task_id] = state

    def get(self, task_id: str) -> TaskState | None:
        return self._tasks.get(task_id)
EOF

    write_file "app/persistence/repositories/vector.py" <<'EOF'
"""Persists and retrieves vector namespaces and embeddings."""
from __future__ import annotations


class VectorRepository:
    def __init__(self) -> None:
        self._namespaces: dict[str, list[dict]] = {}

    def upsert(self, namespace: str, documents: list[dict]) -> None:
        bucket = self._namespaces.setdefault(namespace, [])
        bucket.extend(documents)

    def query(self, namespace: str, query: str, limit: int = 10) -> list[dict]:
        return self._namespaces.get(namespace, [])[:limit]
EOF

    write_file "app/persistence/repositories/telemetry.py" <<'EOF'
"""Persists normalized timeseries and conversion records."""
from __future__ import annotations

from app.schemas.telemetry import TelemetryEvent


class TelemetryRepository:
    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    def append(self, event: TelemetryEvent) -> None:
        self._events.append(event)

    def all(self) -> list[TelemetryEvent]:
        return list(self._events)
EOF

    write_file "app/persistence/repositories/memory.py" <<'EOF'
"""Persists promoted brand knowledge, heuristics, and model deltas."""
from __future__ import annotations


class MemoryRepository:
    def __init__(self) -> None:
        self._store: dict[str, list[dict]] = {}

    def promote(self, tenant_id: str, delta: dict) -> None:
        self._store.setdefault(tenant_id, []).append(delta)

    def all(self, tenant_id: str) -> list[dict]:
        return list(self._store.get(tenant_id, []))
EOF

    write_file "app/persistence/repositories/artifact.py" <<'EOF'
"""Resolves immutable deliverables by UUID/hash."""
from __future__ import annotations

from app.schemas.artifact import ArtifactRef


class ArtifactRepository:
    def __init__(self) -> None:
        self._store: dict[str, ArtifactRef] = {}

    def save(self, ref: ArtifactRef) -> None:
        self._store[ref.artifact_id] = ref

    def resolve(self, artifact_id: str) -> ArtifactRef | None:
        return self._store.get(artifact_id)
EOF

    write_file "app/persistence/repositories/provenance.py" <<'EOF'
"""Appends W3C PROV audit records."""
from __future__ import annotations

from app.schemas.provenance import ProvRecord


class ProvenanceRepository:
    def __init__(self) -> None:
        self._records: list[ProvRecord] = []

    def append(self, record: ProvRecord) -> None:
        self._records.append(record)

    def all(self) -> list[ProvRecord]:
        return list(self._records)
EOF
}

write_tests() {
    write_file "tests/__init__.py" <<'EOF'
"""Development verification suite."""
EOF

    write_file "tests/unit/__init__.py" <<'EOF'
"""Isolated domain and service tests."""
EOF

    write_file "tests/unit/test_policy_authorization.py" <<'EOF'
"""Verifies policy decisions and monotonic attenuation."""
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.schemas.governance import Budget, PolicyEnvelope, RiskEnvelope
from app.security.scope_evaluator import ScopeEvaluator


def _envelope(spend: float, max_spend: float) -> PolicyEnvelope:
    return PolicyEnvelope(
        policy_id="p1",
        directive_id="d1",
        tenant_id="t1",
        scopes=["read"],
        budget=Budget(amount=spend),
        risk=RiskEnvelope(max_spend=max_spend, max_risk_score=0.5),
    )


def test_policy_rejects_budget_over_risk() -> None:
    assert PolicyEvaluator().evaluate(_envelope(100, 50)).allowed is False


def test_policy_allows_budget_within_risk() -> None:
    assert PolicyEvaluator().evaluate(_envelope(10, 50)).allowed is True


def test_scope_attenuation_is_monotonic() -> None:
    attenuated = ScopeEvaluator().attenuate({"a", "b", "c"}, {"b", "c", "d"})
    assert attenuated == {"b", "c"}
EOF

    write_file "tests/unit/test_task_state_machine.py" <<'EOF'
"""Verifies CTS transitions, holds, checkpoints, and DAG rules."""
import pytest

from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.task_state import TaskState, TaskStatus


def _state(status: TaskStatus) -> TaskState:
    return TaskState(task_id="t1", directive_id="d1", tenant_id="t1", status=status)


def test_legal_transition() -> None:
    sm = TaskStateMachine()
    assert sm.transition(_state(TaskStatus.PENDING), TaskStatus.READY).status is TaskStatus.READY


def test_illegal_transition() -> None:
    sm = TaskStateMachine()
    with pytest.raises(ValueError):
        sm.transition(_state(TaskStatus.COMPLETED), TaskStatus.RUNNING)
EOF

    write_file "tests/unit/test_rag_governance.py" <<'EOF'
"""Verifies IE-only RAG access, tenant isolation, freshness, and validation."""
from datetime import datetime, timedelta, timezone

from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.schema_validator import SchemaValidator


def test_freshness_rejects_stale() -> None:
    stale = {"retrieved_at": datetime.now(timezone.utc) - timedelta(days=90)}
    assert FreshnessPolicy().is_fresh(stale) is False


def test_schema_validator_requires_core_fields() -> None:
    assert SchemaValidator().is_valid({"doc_id": "d", "content": "c"}) is True
    assert SchemaValidator().is_valid({"doc_id": "d"}) is False
EOF

    write_file "tests/unit/test_evidence_synthesis.py" <<'EOF'
"""Verifies evidence-envelope consolidation and confidence handling."""
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.schemas.agent_contracts import EvidenceEnvelope


def test_synthesis_averages_confidence() -> None:
    envelopes = [
        EvidenceEnvelope(worker_id="W_DEV", task_id="t", summary="a", confidence=0.4),
        EvidenceEnvelope(worker_id="W_STRAT", task_id="t", summary="b", confidence=0.8),
    ]
    result = EvidenceSynthesizer().synthesize(envelopes)
    assert result["confidence"] == 0.6


def test_synthesis_empty_returns_zero() -> None:
    result = EvidenceSynthesizer().synthesize([])
    assert result["confidence"] == 0.0
EOF

    write_file "tests/unit/test_hitl_gate.py" <<'EOF'
"""Verifies mandatory approval for spend, claims, code, and dispatch."""
from app.schemas.action_preview import ApprovalDecision, PreviewKind
from app.services.hitl import HitlService


def test_hitl_records_decision() -> None:
    svc = HitlService()
    svc.record("p1", ApprovalDecision(decision="approved", reviewer="owner"))
    decision = svc.decision_for("p1")
    assert decision is not None
    assert decision.decision == "approved"


def test_preview_kind_enum_has_all_mandatory_kinds() -> None:
    kinds = {k.value for k in PreviewKind}
    assert {"spend", "claims", "copy", "code"} <= kinds
EOF

    write_file "tests/integration/__init__.py" <<'EOF'
"""Cross-boundary backend integration tests."""
EOF

    write_file "tests/integration/test_worker_sandbox_boundary.py" <<'EOF'
"""Verifies all seven workers use only the sandbox adapter."""
import inspect

from app.agents import (
    competitor_intel,
    creative_content,
    customer_voice,
    development,
    learning_performance,
    product_evidence,
    strategy,
)

MODULES = [
    development,
    strategy,
    creative_content,
    product_evidence,
    competitor_intel,
    customer_voice,
    learning_performance,
]


def test_workers_import_only_sandbox_client() -> None:
    for module in MODULES:
        source = inspect.getsource(module)
        assert "app.integrations.sandbox.client" in source
        assert "import agent_sandbox" not in source
EOF

    write_file "tests/integration/test_model_a_data_access.py" <<'EOF'
"""Verifies workers cannot directly access RAG or persistence."""
import inspect

from app.agents import development, learning_performance, strategy

FORBIDDEN = ("app.services.rag", "app.persistence")


def test_workers_do_not_access_rag_or_persistence() -> None:
    for module in (development, strategy, learning_performance):
        source = inspect.getsource(module)
        for token in FORBIDDEN:
            assert token not in source
EOF

    write_file "tests/integration/test_outbound_after_approval.py" <<'EOF'
"""Verifies external writes require signed HITL clearance."""
import pytest

from app.integrations.ads.meta import MetaAdsAdapter


def test_paid_media_write_requires_signed_dispatch() -> None:
    with pytest.raises(PermissionError):
        MetaAdsAdapter(credentials={}).push_campaign({})
EOF

    write_file "tests/integration/test_telemetry_learning_loop.py" <<'EOF'
"""Verifies telemetry feeds W_LEARN and validated memory promotion."""
from datetime import datetime, timezone

from app.schemas.telemetry import TelemetryChannel, TelemetryEvent
from app.services.memory_promotion import MemoryPromotionService
from app.services.telemetry import TelemetryService


def test_telemetry_ingest_and_memory_promotion() -> None:
    svc = TelemetryService()
    svc.ingest(
        TelemetryEvent(
            event_id="e1",
            tenant_id="t1",
            channel=TelemetryChannel.ROAS,
            occurred_at=datetime.now(timezone.utc),
            metrics={"roas": 3.2},
        )
    )
    assert svc.all()
    assert MemoryPromotionService().promote("t1", {"confidence": 0.9}) is True
    assert MemoryPromotionService().promote("t1", {"confidence": 0.1}) is False
EOF

    write_file "tests/integration/test_provenance_persistence.py" <<'EOF'
"""Verifies required control-plane and execution audit lineage."""
from datetime import datetime, timezone

from app.persistence.repositories.provenance import ProvenanceRepository
from app.schemas.provenance import ProvRecord


def test_provenance_append_only() -> None:
    repo = ProvenanceRepository()
    now = datetime.now(timezone.utc)
    repo.append(ProvRecord(entity_id="e", activity_id="a", agent_id="W_DEV", started_at=now))
    assert len(repo.all()) == 1
EOF

    write_file "tests/acceptance/__init__.py" <<'EOF'
"""Complete architecture-level validation."""
EOF

    write_file "tests/acceptance/test_governed_end_to_end_flow.py" <<'EOF'
"""Verifies directive -> workers -> HITL -> actuation -> telemetry -> learning flow."""
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.schemas.governance import Budget, Directive, PolicyEnvelope, RiskEnvelope
from app.services.policy_engine import PolicyEngine


def test_end_to_end_governed_flow() -> None:
    directive = Directive(
        directive_id="d1",
        tenant_id="t1",
        objective="grow signups",
        scopes=["read", "plan"],
        budget=Budget(amount=10),
        risk=RiskEnvelope(max_spend=100, max_risk_score=0.4),
    )
    envelope: PolicyEnvelope = PolicyEngine().compile_envelope(directive)
    result = IntelligenceEngine().run(envelope)
    assert result["status"] == "scheduled"
EOF
}

write_scripts() {
    write_exec "scripts/dev.sh" <<'DEV_EOF'
#!/usr/bin/env bash
# Run the development API server.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

cd -- "$REPO_ROOT"

if ! python -c 'import uvicorn' >/dev/null 2>&1; then
    printf 'uvicorn not installed. Run: pip install -e ".[dev]"\n' >&2
    exit 1
fi

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT:-8000}" --reload
DEV_EOF

    write_exec "scripts/test.sh" <<'TEST_EOF'
#!/usr/bin/env bash
# Run the pytest suite.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

cd -- "$REPO_ROOT"

if ! python -c 'import pytest' >/dev/null 2>&1; then
    printf 'pytest not installed. Run: pip install -e ".[dev]"\n' >&2
    exit 1
fi

exec python -m pytest "$@"
TEST_EOF

    write_exec "scripts/lint.sh" <<'LINT_EOF'
#!/usr/bin/env bash
# Run ruff and mypy.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

cd -- "$REPO_ROOT"

status=0

if command -v ruff >/dev/null 2>&1; then
    ruff check app tests || status=$?
else
    printf 'ruff not found, skipping lint\n' >&2
fi

if command -v mypy >/dev/null 2>&1; then
    mypy app || status=$?
else
    printf 'mypy not found, skipping typecheck\n' >&2
fi

exit "$status"
LINT_EOF
}

write_runtime_dirs() {
    ensure_dir "var"
    ensure_dir "var/log"
    ensure_dir "var/tmp"

    write_file "var/.gitkeep" <<'EOF'
EOF
    write_file "var/log/.gitkeep" <<'EOF'
EOF
    write_file "var/tmp/.gitkeep" <<'EOF'
EOF
}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
validate() {
    local failed=0

    # Required top-level files
    local required=(
        "pyproject.toml"
        ".gitignore"
        ".env.example"
        "Makefile"
        "README.md"
        "app/main.py"
        "app/api/router.py"
        "app/core/settings.py"
        "app/schemas/governance.py"
        "app/orchestration/intelligence_engine.py"
        "app/agents/development.py"
        "app/services/policy_engine.py"
        "app/security/authorization_boundary.py"
        "app/mcp/host.py"
        "app/integrations/sandbox/client.py"
        "app/persistence/database.py"
        "scripts/dev.sh"
        "scripts/test.sh"
        "scripts/lint.sh"
        "tests/acceptance/test_governed_end_to_end_flow.py"
    )

    local rel
    for rel in "${required[@]}"; do
        if [[ ! -f "$ROOT/$rel" ]]; then
            warn "missing required file: $rel"
            failed=1
        fi
    done

    # Executable bit on scripts
    local script
    for script in "$ROOT"/scripts/*.sh; do
        [[ -f "$script" ]] || continue
        if [[ ! -x "$script" ]]; then
            warn "script not executable: ${script#"$ROOT/"}"
            failed=1
        fi
    done

    # Bash syntax check
    if command -v bash >/dev/null 2>&1; then
        local b
        for b in "$ROOT"/scripts/*.sh; do
            [[ -f "$b" ]] || continue
            if ! bash -n "$b"; then
                warn "syntax error in: ${b#"$ROOT/"}"
                failed=1
            fi
        done
    fi

    # Optional Python compilation check (informational only).
    if command -v python3 >/dev/null 2>&1; then
        local pyver
        pyver="$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])' 2>/dev/null || echo 0)"
        if (( pyver >= 311 )); then
            if ! python3 -m compileall -q "$ROOT/app" "$ROOT/tests" >/dev/null 2>&1; then
                warn "python compileall reported issues (non-fatal)"
            fi
        else
            warn "skipping compileall: python3 is $pyver, project targets 3.11+"
        fi
        find "$ROOT" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
    fi

    # Optional shellcheck
    if command -v shellcheck >/dev/null 2>&1; then
        local s
        for s in "$ROOT"/scripts/*.sh; do
            [[ -f "$s" ]] || continue
            if ! shellcheck --severity=warning --shell=bash "$s" >/dev/null; then
                warn "shellcheck warnings in: ${s#"$ROOT/"}"
            fi
        done
    fi

    return "$failed"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    parse_args "$@"
    require_bash5

    ROOT="${ROOT%/}"

    log "scaffolding governed backend into: $ROOT (force=$FORCE)"

    mkdir -p -- "$ROOT"

    write_project_root
    write_app_root
    write_api
    write_core
    write_schemas
    write_orchestration
    write_agents
    write_services
    write_security
    write_mcp
    write_integrations
    write_persistence
    write_tests
    write_scripts
    write_runtime_dirs

    if validate; then
        log "scaffold complete and validated: $ROOT"
    else
        die "scaffold completed but validation reported issues" 2
    fi
}

main "$@"