from app.api.deps import get_current_user
from app.core.rbac import UserRole, check_permission
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("")
async def get_settings(current_user: dict = Depends(get_current_user)):
    return {
        "encryption": "AES-256-GCM",
        "sandbox_engine": "rootless-podman",
        "primary_observability": "Langfuse (OTLP)",
        "checkpointer": "PostgresSaver (Async)",
        "target_platforms_count": 8,
    }

@router.patch("")
async def update_settings(payload: dict, current_user: dict = Depends(get_current_user)):
    check_permission(current_user["role"], [UserRole.ADMIN])
    return {"status": "saved", "settings": payload}
