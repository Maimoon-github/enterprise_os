from typing import Any

from app.api.deps import get_current_user, require_role
from app.core.rbac import UserRole
from app.schemas.common import SettingsResponse, SettingsUpdateRequest
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("", response_model=SettingsResponse)
async def get_settings(current_user: dict[str, Any] = Depends(get_current_user)):
    return SettingsResponse(
        encryption="AES-256-GCM",
        sandbox_engine="rootless-podman",
        primary_observability="Langfuse (OTLP)",
        checkpointer="PostgresSaver (Async)",
        target_platforms_count=8,
    )


@router.patch("", response_model=dict[str, Any])
async def update_settings(
    payload: SettingsUpdateRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.ADMIN)),
):
    return {"status": "saved", "settings": payload.settings}
