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
