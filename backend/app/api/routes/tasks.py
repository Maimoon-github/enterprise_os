"""Exposes canonical task-state and workflow status operations."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.task_state import CanonicalTaskState

router = APIRouter()


@router.get("/{task_id}", response_model=CanonicalTaskState)
async def get_task(task_id: str, request: Request) -> CanonicalTaskState:
    """Return the canonical task state for ``task_id``."""

    task_state_repository = request.app.state.task_state_repository
    return await task_state_repository.require(task_id)


@router.get("/directive/{directive_id}", response_model=list[CanonicalTaskState])
async def list_tasks_for_directive(directive_id: str, request: Request) -> list[CanonicalTaskState]:
    """Return every task state associated with ``directive_id``."""

    task_state_repository = request.app.state.task_state_repository
    return await task_state_repository.list_by_directive(directive_id)