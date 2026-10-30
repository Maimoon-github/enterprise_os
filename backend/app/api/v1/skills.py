from pathlib import Path
from typing import Any

from app.api.deps import get_current_user, require_role
from app.core.rbac import UserRole
from app.schemas.skill import SkillSummary, SkillValidateRequest, SkillValidateResponse
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("", response_model=list[SkillSummary])
async def list_skills(current_user: dict[str, Any] = Depends(get_current_user)):
    skills_dir = Path("skills")
    results = []
    if skills_dir.exists():
        for skill_path in sorted(skills_dir.iterdir()):
            if skill_path.is_dir() and (skill_path / "SKILL.md").exists():
                results.append(
                    SkillSummary(
                        name=skill_path.name,
                        path=str(skill_path / "SKILL.md"),
                        description=f"Skill package for {skill_path.name}",
                        status="valid",
                        tier="progressive_disclosure",
                        valid=True,
                    )
                )
    if not results:
        results = [
            SkillSummary(
                name="brand_voice_guidelines",
                path="skills/brand_voice_guidelines/SKILL.md",
                description="Tone of voice and stylistic guardrails",
                tier="progressive_disclosure",
                valid=True,
            ),
            SkillSummary(
                name="creative_copy_generation",
                path="skills/creative_copy_generation/SKILL.md",
                description="Structured post crafting across 8 channels",
                tier="progressive_disclosure",
                valid=True,
            ),
        ]
    return results


@router.post("/validate", response_model=SkillValidateResponse)
async def validate_skill(
    payload: SkillValidateRequest,
    current_user: dict[str, Any] = Depends(require_role(UserRole.OPERATOR)),
):
    errors = []
    if not payload.name:
        errors.append("Skill name cannot be empty")
    if not payload.content or "---" not in payload.content:
        errors.append("Skill content must contain YAML frontmatter delimited by '---'")

    token_estimate = len(payload.content.split()) * 2
    return SkillValidateResponse(
        valid=len(errors) == 0,
        errors=errors,
        token_estimate=token_estimate,
    )
