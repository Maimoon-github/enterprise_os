import re
from pathlib import Path
from typing import Any

from app.schemas.skill import SkillDetailResponse, SkillSummary, SkillValidateResponse
from app.services.sandbox_service import SandboxService

NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ALLOWED_TIER3_DIRS = {"scripts", "references", "assets"}


class SkillService:
    """Manages the lifecycle of agentskills.io progressive-disclosure packages (Tiers 1, 2, 3)."""

    def __init__(self, base_path: Path | None = None):
        self.base_path = base_path or self._resolve_skills_dir()

    @staticmethod
    def _resolve_skills_dir() -> Path:
        candidates = [
            Path(__file__).resolve().parent.parent.parent / "skills",
            Path("backend/skills"),
            Path("skills"),
        ]
        for c in candidates:
            if c.exists() and c.is_dir():
                return c.resolve()
        return (Path(__file__).resolve().parent.parent.parent / "skills").resolve()

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict[str, str], str, list[str]]:
        errors = []
        if not content.startswith("---"):
            return {}, content, ["Missing opening '---' YAML frontmatter delimiter"]

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content, ["Missing closing '---' YAML frontmatter delimiter"]

        fm_raw = parts[1].strip()
        body = parts[2].strip()

        metadata: dict[str, str] = {}
        for line in fm_raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                errors.append(f"Invalid YAML frontmatter line: '{line}'")
                continue
            key, val = line.split(":", 1)
            metadata[key.strip()] = val.strip().strip("\"'")

        return metadata, body, errors

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        words = len(text.split())
        chars = len(text)
        return max(int(words * 1.3), chars // 4, 1) if text.strip() else 0

    def list_skills(self) -> list[SkillSummary]:
        """Scan skills directory and return Tier 1 metadata summaries for all packages."""
        if not self.base_path.exists():
            return []

        skills = []
        for s_dir in sorted(self.base_path.iterdir()):
            if not s_dir.is_dir():
                continue
            skill_md = s_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            content = skill_md.read_text(encoding="utf-8")
            metadata, body, errors = self._parse_frontmatter(content)
            lines_count = len(content.splitlines())
            tokens = self._estimate_tokens(content)

            tier3_files = []
            for sub in s_dir.iterdir():
                if sub.is_dir() and sub.name in ALLOWED_TIER3_DIRS:
                    for f in sub.iterdir():
                        if f.is_file():
                            tier3_files.append(str(f.relative_to(s_dir)))

            allowed_tools_raw = metadata.get("allowed-tools", "")
            allowed_tools = (
                []
                if allowed_tools_raw.lower() in ("none", "")
                else allowed_tools_raw.split()
            )

            skills.append(
                SkillSummary(
                    name=s_dir.name,
                    path=str(skill_md),
                    description=metadata.get("description", f"Skill package for {s_dir.name}"),
                    compatibility=metadata.get("compatibility"),
                    allowed_tools=allowed_tools,
                    tier="Tier 1/2/3",
                    status="validated" if not errors else "invalid",
                    valid=len(errors) == 0,
                    lines_count=lines_count,
                    token_estimate=tokens,
                    tier3_resources=sorted(tier3_files),
                )
            )
        return skills

    def get_skill(self, skill_name: str) -> SkillDetailResponse | None:
        """Retrieve full skill representation including Tier 2 body and Tier 3 resources."""
        skill_dir = self.base_path / skill_name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        content = skill_md.read_text(encoding="utf-8")
        metadata, body, _ = self._parse_frontmatter(content)
        lines_count = len(content.splitlines())
        tokens = self._estimate_tokens(content)

        tier3_files = []
        for sub in skill_dir.iterdir():
            if sub.is_dir() and sub.name in ALLOWED_TIER3_DIRS:
                for f in sub.iterdir():
                    if f.is_file():
                        tier3_files.append(str(f.relative_to(skill_dir)))

        allowed_tools_raw = metadata.get("allowed-tools", "")
        allowed_tools = (
            []
            if allowed_tools_raw.lower() in ("none", "")
            else allowed_tools_raw.split()
        )

        return SkillDetailResponse(
            name=skill_name,
            path=str(skill_md),
            description=metadata.get("description", ""),
            compatibility=metadata.get("compatibility"),
            allowed_tools=allowed_tools,
            tier="Tier 1/2/3",
            status="validated",
            valid=True,
            lines_count=lines_count,
            token_estimate=tokens,
            tier3_resources=sorted(tier3_files),
            content=content,
            tier2_body=body,
        )

    def load_skill_body(self, skill_name: str) -> str:
        """Tier 2 on-demand loader: load only instruction body when skill is activated."""
        skill_md = self.base_path / skill_name / "SKILL.md"
        if not skill_md.exists():
            return ""
        content = skill_md.read_text(encoding="utf-8")
        _, body, _ = self._parse_frontmatter(content)
        return body

    def load_tier3_resource(self, skill_name: str, relative_path: str) -> str:
        """Tier 3 on-demand loader with strict path-traversal prevention."""
        skill_dir = (self.base_path / skill_name).resolve()
        target_path = (skill_dir / relative_path).resolve()

        if not str(target_path).startswith(str(skill_dir)):
            raise ValueError(f"Path traversal detected: {relative_path} escapes {skill_dir}")

        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"Tier 3 resource not found: {relative_path}")

        return target_path.read_text(encoding="utf-8")

    def execute_skill_script(
        self,
        skill_name: str,
        script_name: str,
        stdin_data: str = "",
    ) -> dict[str, Any]:
        """Execute Tier 3 script inside rootless Podman sandbox."""
        skill_dir = (self.base_path / skill_name).resolve()
        script_path = (skill_dir / "scripts" / script_name).resolve()

        if not str(script_path).startswith(str(skill_dir)):
            raise ValueError(f"Path traversal detected in script path: {script_name}")
        if not script_path.exists():
            raise FileNotFoundError(f"Tier 3 script not found: {script_name}")

        code = script_path.read_text(encoding="utf-8")
        return SandboxService.run_isolated_command(
            code,
            is_content=True,
            input_data=stdin_data,
        )

    def validate_skill_content(self, name: str, content: str) -> SkillValidateResponse:
        """Validate proposed or updated skill content against agentskills.io schema."""
        errors: list[str] = []
        if not name:
            errors.append("Skill name cannot be empty")
        elif not NAME_PATTERN.match(name):
            errors.append(f"Invalid skill name '{name}': must be lowercase alphanumeric with hyphens")

        metadata, body, fm_errors = self._parse_frontmatter(content)
        errors.extend(fm_errors)

        if "name" in metadata and metadata["name"] != name:
            errors.append(f"Frontmatter name '{metadata['name']}' does not match requested name '{name}'")

        if not metadata.get("description"):
            errors.append("Missing mandatory 'description' in YAML frontmatter")

        lines_count = len(content.splitlines())
        body_lines = len(body.splitlines())
        tokens = self._estimate_tokens(content)

        if body_lines >= 500:
            errors.append(f"Tier 2 body exceeds 500 lines limit ({body_lines})")
        if tokens >= 5000:
            errors.append(f"Tier 2 body exceeds 5,000 tokens limit ({tokens})")

        return SkillValidateResponse(
            valid=len(errors) == 0,
            errors=errors,
            token_estimate=tokens,
            lines_count=lines_count,
        )

    def get_tier1_catalog(self) -> list[dict[str, Any]]:
        """Compact Tier 1 catalog (~100 tokens per skill) loaded at startup."""
        skills = self.list_skills()
        return [
            {
                "name": s.name,
                "description": s.description,
                "allowed_tools": s.allowed_tools,
                "compatibility": s.compatibility,
            }
            for s in skills
        ]


skill_service = SkillService()
