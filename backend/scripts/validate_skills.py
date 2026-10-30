from pathlib import Path
import re
import sys

def validate():
    skills_dir = Path("skills")
    if not skills_dir.exists():
        print("No skills directory found.")
        sys.exit(1)

    errors = []
    for skill_path in skills_dir.iterdir():
        if skill_path.is_dir():
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                errors.append(f"{skill_path.name}: Missing SKILL.md")
                continue
            content = skill_md.read_text()
            if not content.startswith("---"):
                errors.append(f"{skill_path.name}: SKILL.md missing YAML frontmatter")

    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        sys.exit(1)
    print("All skills validated successfully.")

if __name__ == "__main__":
    validate()
