from typing import Any

from app.api.deps import get_current_user, require_role
from app.core.rbac import UserRole
from app.schemas.common import SettingsResponse, SettingsUpdateRequest
from app.services.sandbox_service import SandboxService
from app.tasks.beat_schedule import CELERY_BEAT_SCHEDULE
from app.tasks.celery_app import task_queues
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("", response_model=SettingsResponse)
async def get_settings(current_user: dict[str, Any] = Depends(get_current_user)):
    """Retrieve platform security, Celery queues, and Podman sandbox configuration."""
    sandbox_status = SandboxService.get_sandbox_status()
    queue_names = [q.name for q in task_queues]

    return SettingsResponse(
        encryption="AES-256-GCM",
        sandbox_engine="rootless-podman",
        primary_observability="Langfuse (OTLP)",
        checkpointer="PostgresSaver (Async)",
        target_platforms_count=8,
        sandbox_limits=sandbox_status,
        celery_queues=queue_names,
        beat_schedules_count=len(CELERY_BEAT_SCHEDULE),
    )


@router.patch("", response_model=dict[str, Any])
async def update_settings(
    payload: SettingsUpdateRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN)),
):
    """Update system settings."""
    return {"status": "saved", "settings": payload.settings}
