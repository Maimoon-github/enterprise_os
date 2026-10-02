"""Accepts owner objectives, scopes, budgets, and risk directives.

Provides CRUD endpoints and the critical orchestration trigger that connects
a persisted directive to the Intelligence Engine planning and DAG execution
pipeline.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel, Field

from app.core.exceptions import AuthorizationError, PolicyViolationError
from app.core.logging import get_logger
from app.orchestration.intelligence_engine import IntelligenceResult, PlanStep
from app.schemas.governance import Directive, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskDependency, TaskStatus

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models for the execute endpoint
# ---------------------------------------------------------------------------


class ExecutionTaskInfo(BaseModel):
    """Summary of a CTS task created during orchestration."""

    task_id: str
    directive_id: str
    worker_role: str
    status: str
    step_id: str


class DirectiveExecutionResponse(BaseModel):
    """Response from the directive orchestration trigger."""

    directive_id: str
    status: str = "orchestrating"
    plan: IntelligenceResult | None = None
    tasks_created: list[ExecutionTaskInfo] = Field(default_factory=list)
    message: str = ""


# ---------------------------------------------------------------------------
# Background DAG execution runner
# ---------------------------------------------------------------------------


async def _run_dag_in_background(
    *,
    intelligence_engine: Any,
    directive: Directive,
    tasks: list[CanonicalTaskState],
    task_state_service: Any,
) -> None:
    """Execute the DAG tasks via the Intelligence Engine.

    This runs inside a FastAPI ``BackgroundTasks`` callback so the HTTP response
    returns immediately while the long-running LLM orchestration proceeds.
    """
    try:
        logger.info(
            "Starting DAG execution for directive '%s' with %d tasks",
            directive.directive_id,
            len(tasks),
        )
        envelopes = await intelligence_engine.execute_dag(
            directive, tasks, task_state_service=task_state_service
        )
        logger.info(
            "DAG execution completed for directive '%s': %d envelopes",
            directive.directive_id,
            len(envelopes),
        )
    except Exception:
        logger.exception(
            "DAG execution failed for directive '%s'", directive.directive_id
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=Directive, status_code=201)
async def create_directive(directive: Directive, request: Request) -> Directive:
    """Accept and persist a new owner-issued directive with tenant authority validation."""

    if not directive.validate_tenant_consistency():
        raise PolicyViolationError(
            f"Directive tenant_id '{directive.tenant_id}' does not match scope tenant_id '{directive.scope.tenant_id}'."
        )

    auth_tenant = getattr(request.state, "tenant_id", None) or request.headers.get("x-tenant-id")
    if auth_tenant and auth_tenant not in ("*", "default", "global"):
        if directive.tenant_id != auth_tenant:
            raise AuthorizationError(
                f"Tenant authority mismatch: authenticated tenant '{auth_tenant}' "
                f"cannot issue directive for tenant '{directive.tenant_id}'."
            )

    operational_repository = request.app.state.operational_repository
    await operational_repository.save_directive(directive)
    return directive


@router.get("", response_model=list[Directive])
async def list_directives(request: Request) -> list[Directive]:
    """Return all directives for the authenticated tenant.

    Uses the ``X-Tenant-Id`` header (or defaults to ``default``) to scope
    the listing via the repository's ``list_by_tenant`` method.
    """
    tenant_id = (
        getattr(request.state, "tenant_id", None)
        or request.headers.get("x-tenant-id")
        or "default"
    )
    operational_repository = request.app.state.operational_repository
    return await operational_repository.list_by_tenant(tenant_id)


@router.get("/{directive_id}", response_model=Directive)
async def get_directive(directive_id: str, request: Request) -> Directive:
    """Return a previously accepted directive."""

    operational_repository = request.app.state.operational_repository
    return await operational_repository.require(directive_id)


@router.post("/{directive_id}/execute", response_model=DirectiveExecutionResponse)
async def execute_directive(
    directive_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> DirectiveExecutionResponse:
    """Orchestration trigger: plan the directive and execute the resulting DAG.

    1. Retrieves the persisted directive.
    2. Calls ``IntelligenceEngine.plan_directive()`` to generate an LLM-derived DAG.
    3. Creates a ``CanonicalTaskState`` for each plan step and persists via ``TaskStateService``.
    4. Wires inter-task DAG dependencies as ``TaskDependency`` edges.
    5. Enqueues ``IntelligenceEngine.execute_dag()`` as a background task so the HTTP
       response returns immediately while the long-running worker orchestration proceeds.
    """
    operational_repository = request.app.state.operational_repository
    intelligence_engine = request.app.state.intelligence_engine
    task_state_service = request.app.state.task_state_service

    # 1. Fetch the persisted directive
    directive = await operational_repository.require(directive_id)

    # 2. Intelligence Engine cognitive planning via live LLM
    plan_result: IntelligenceResult = await intelligence_engine.plan_directive(
        directive, available_workers=list(WorkerRole)
    )

    # 3. Mint CTS tasks for every plan step using two deterministic passes

    # Pass 1: Validate unique step_ids and allocate every task_id
    step_id_to_task_id: dict[str, str] = {}
    for step in plan_result.plan:
        if not step.step_id or not step.step_id.strip():
            raise PolicyViolationError("Plan step must have a non-empty step_id.")
        step_id = step.step_id.strip()
        if step_id in step_id_to_task_id:
            raise PolicyViolationError(f"Duplicate step_id '{step_id}' found in plan.")
        step_id_to_task_id[step_id] = f"task-{uuid.uuid4()}"

    # Pass 2: Resolve all declared dependencies from the complete mapping and create/persist CTS tasks
    created_tasks: list[CanonicalTaskState] = []
    task_infos: list[ExecutionTaskInfo] = []

    for step in plan_result.plan:
        step_id = step.step_id.strip()
        task_id = step_id_to_task_id[step_id]

        dependencies: list[TaskDependency] = []
        for dep_step_id in step.dependencies:
            dep_clean = dep_step_id.strip() if isinstance(dep_step_id, str) else ""
            if not dep_clean:
                raise PolicyViolationError(
                    f"Malformed empty dependency declared by plan step '{step_id}'."
                )
            if dep_clean == step_id:
                raise PolicyViolationError(
                    f"Self-dependency detected: step '{step_id}' cannot depend on itself."
                )
            if dep_clean not in step_id_to_task_id:
                raise PolicyViolationError(
                    f"Unknown dependency '{dep_clean}' declared by plan step '{step_id}'."
                )
            upstream_task_id = step_id_to_task_id[dep_clean]
            dependencies.append(
                TaskDependency(
                    upstream_task_id=upstream_task_id,
                    downstream_task_id=task_id,
                )
            )

        task_state = CanonicalTaskState(
            task_id=task_id,
            directive_id=directive.directive_id,
            tenant_id=directive.tenant_id,
            worker_role=step.recommended_worker or WorkerRole.DEVELOPMENT,
            status=TaskStatus.PENDING,
            dependencies=dependencies,
        )
        await task_state_service.save_state(directive.tenant_id, task_state)
        created_tasks.append(task_state)

        task_infos.append(
            ExecutionTaskInfo(
                task_id=task_id,
                directive_id=directive.directive_id,
                worker_role=(step.recommended_worker or WorkerRole.DEVELOPMENT).value,
                status=TaskStatus.PENDING.value,
                step_id=step_id,
            )
        )

    logger.info(
        "Directive '%s' planned: %d steps, %d CTS tasks created",
        directive_id,
        len(plan_result.plan),
        len(created_tasks),
    )

    # 4. Enqueue DAG execution as a background task
    if created_tasks:
        background_tasks.add_task(
            _run_dag_in_background,
            intelligence_engine=intelligence_engine,
            directive=directive,
            tasks=created_tasks,
            task_state_service=task_state_service,
        )

    return DirectiveExecutionResponse(
        directive_id=directive.directive_id,
        status="orchestrating",
        plan=plan_result,
        tasks_created=task_infos,
        message=(
            f"Intelligence Engine generated {len(plan_result.plan)} plan steps. "
            f"{len(created_tasks)} CTS tasks created and DAG execution enqueued."
        ),
    )