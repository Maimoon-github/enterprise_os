from typing import Any

from app.api.deps import get_current_user, require_role
from app.core.exceptions import EntityNotFoundError
from app.core.rbac import UserRole
from app.schemas.skill import (
    SkillDetailResponse,
    SkillSummary,
    SkillValidateRequest,
    SkillValidateResponse,
)
from app.services.skill_service import skill_service
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("", response_model=list[SkillSummary])
async def list_skills(current_user: dict[str, Any] = Depends(get_current_user)):
    """Retrieve catalog of all agent skills with Tier 1 metadata and validation badges."""
    return skill_service.list_skills()


@router.get("/{skill_name}", response_model=SkillDetailResponse)
async def get_skill(
    skill_name: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve full skill specification including Tier 2 instructions and Tier 3 resources."""
    skill = skill_service.get_skill(skill_name)
    if not skill:
        raise EntityNotFoundError("Skill", skill_name)
    return skill


@router.post("/validate", response_model=SkillValidateResponse)
async def validate_skill(
    payload: SkillValidateRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.OPERATOR)),
):
    """Validate skill content against the agentskills.io progressive-disclosure specification."""
    return skill_service.validate_skill_content(payload.name, payload.content)
