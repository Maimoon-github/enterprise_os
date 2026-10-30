from pathlib import Path


class SkillService:
    def load_skill_body(self, skill_name: str) -> str:
        skill_file = Path("skills") / skill_name / "SKILL.md"
        return skill_file.read_text() if skill_file.exists() else ""
