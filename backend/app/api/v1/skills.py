from fastapi import APIRouter
from pathlib import Path

router = APIRouter()

@router.get("")
async def list_skills():
    skills_dir = Path("skills")
    results = []
    if skills_dir.exists():
        for skill_path in skills_dir.iterdir():
            if skill_path.is_dir() and (skill_path / "SKILL.md").exists():
                results.append({
                    "name": skill_path.name,
                    "path": str(skill_path / "SKILL.md"),
                    "status": "valid",
                    "tier": "progressive_disclosure",
                })
    return results
