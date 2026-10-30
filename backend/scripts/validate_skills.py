import sys
from pathlib import Path


def validate():
    # Support execution from repo root, backend/, or anywhere
    base_dir = Path(__file__).resolve().parent.parent
    skills_dir = base_dir / "skills"
    if not skills_dir.exists():
        skills_dir = Path("skills")
    if not skills_dir.exists():
        print("No skills directory found.")
        sys.exit(1)

    errors = []
    skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
    if not skill_dirs:
        print("No skill packages present in skills directory.")
        return

    for skill_path in skill_dirs:
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
