#!/usr/bin/env python3
"""CI Skill Validator for agentskills.io Progressive Disclosure Specification.

Enforces:
1. YAML frontmatter schema (name, description, compatibility, allowed-tools)
2. Directory name exact match
3. Tier 1 metadata budget (~100 tokens)
4. Tier 2 instruction budget (<500 lines, <5,000 tokens)
5. Tier 3 resource structure (scripts/, references/, assets/ strictly 1 level deep)
6. Tier 3 resource syntax validation (Python AST, JSON syntax)
7. Subprocess execution of `skills-ref validate` when present on PATH.
"""
import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ALLOWED_TIER3_DIRS = {"scripts", "references", "assets"}


def estimate_tokens(text: str) -> int:
    """Deterministic token estimation heuristic (words * 1.3)."""
    words = len(text.split())
    chars = len(text)
    return max(int(words * 1.3), chars // 4, 1) if text.strip() else 0


def parse_frontmatter(content: str) -> tuple[dict[str, str], str, list[str]]:
    """Parse and extract YAML frontmatter delimited by '---'."""
    errors = []
    if not content.startswith("---"):
        return {}, content, ["Missing opening '---' frontmatter delimiter"]

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content, ["Missing closing '---' frontmatter delimiter"]

    fm_raw = parts[1].strip()
    body = parts[2].strip()

    metadata: dict[str, str] = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            errors.append(f"Invalid YAML frontmatter line (missing colon): '{line}'")
            continue
        key, val = line.split(":", 1)
        metadata[key.strip()] = val.strip().strip("\"'")

    return metadata, body, errors


def validate_single_skill(skill_dir: Path) -> dict[str, Any]:
    """Validate a single skill package against agentskills.io rubric."""
    errors: list[str] = []
    warnings: list[str] = []
    dir_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return {
            "name": dir_name,
            "path": str(skill_dir),
            "valid": False,
            "errors": [f"Missing mandatory SKILL.md in {skill_dir}"],
            "warnings": [],
            "token_estimate": 0,
            "lines_count": 0,
            "tier3_files": [],
        }

    raw_content = skill_md.read_text(encoding="utf-8")
    lines_count = len(raw_content.splitlines())
    metadata, body, fm_errors = parse_frontmatter(raw_content)
    errors.extend(fm_errors)

    # 1. Name validation
    name = metadata.get("name", "")
    if not name:
        errors.append("Missing mandatory 'name' in YAML frontmatter")
    elif len(name) > 64:
        errors.append(f"Skill name '{name}' exceeds 64 characters limit ({len(name)})")
    elif not NAME_PATTERN.match(name):
        errors.append(f"Skill name '{name}' violates format: must be lowercase alphanumeric with hyphens")
    elif name != dir_name:
        errors.append(f"Skill name '{name}' does not match directory name '{dir_name}'")

    # 2. Description validation
    desc = metadata.get("description", "")
    if not desc:
        errors.append("Missing mandatory 'description' in YAML frontmatter")
    elif len(desc) > 1024:
        errors.append(f"Skill description exceeds 1024 characters limit ({len(desc)})")
    else:
        desc_lower = desc.lower()
        if "activate" not in desc_lower and "when" not in desc_lower and "during" not in desc_lower:
            warnings.append("Description should clearly state when the orchestrator/worker should activate it")

    # 3. Compatibility validation
    compat = metadata.get("compatibility")
    if compat and len(compat) > 500:
        errors.append(f"Compatibility declaration exceeds 500 characters ({len(compat)})")

    # 4. Allowed tools validation
    allowed_tools = metadata.get("allowed-tools", "")
    if not allowed_tools:
        warnings.append("No 'allowed-tools' declared in frontmatter (consider specifying tools or 'none')")

    # 5. Token budgets
    tier1_text = f"{name} {desc}"
    tier1_tokens = estimate_tokens(tier1_text)
    if tier1_tokens > 200:
        warnings.append(f"Tier 1 metadata is large (~{tier1_tokens} tokens); target is ~100 tokens")

    tier2_tokens = estimate_tokens(body)
    tier2_lines = len(body.splitlines())
    if tier2_lines >= 500:
        errors.append(f"Tier 2 instructions exceed 500 lines budget ({tier2_lines} lines)")
    if tier2_tokens >= 5000:
        errors.append(f"Tier 2 instructions exceed 5,000 tokens budget ({tier2_tokens} tokens)")

    # 6. Tier 3 Resource Validation
    tier3_files: list[str] = []
    for item in skill_dir.iterdir():
        if item.name == "SKILL.md":
            continue
        if item.is_dir():
            if item.name not in ALLOWED_TIER3_DIRS:
                errors.append(f"Invalid subdirectory '{item.name}'. Only 'scripts', 'references', 'assets' are allowed")
                continue
            # Must be strictly 1 level deep
            for sub_item in item.iterdir():
                if sub_item.is_dir():
                    errors.append(f"Tier 3 resources must be strictly 1 level deep: nested dir found '{sub_item.relative_to(skill_dir)}'")
                else:
                    rel_path = str(sub_item.relative_to(skill_dir))
                    tier3_files.append(rel_path)
                    # Syntax validation
                    if sub_item.suffix == ".py":
                        try:
                            ast.parse(sub_item.read_text(encoding="utf-8"))
                        except Exception as e:
                            errors.append(f"Invalid Python syntax in {rel_path}: {e}")
                    elif sub_item.suffix == ".json":
                        try:
                            json.loads(sub_item.read_text(encoding="utf-8"))
                        except Exception as e:
                            errors.append(f"Invalid JSON syntax in {rel_path}: {e}")
                    elif (
                        sub_item.suffix == ".md"
                        and not sub_item.read_text(encoding="utf-8").strip()
                    ):
                        errors.append(f"Reference file {rel_path} is empty")
        else:
            errors.append(f"Unexpected file in skill root: '{item.name}'. Tier 3 files must reside in scripts/, references/, or assets/")

    # 7. skills-ref CLI compatibility if present
    skills_ref_bin = shutil.which("skills-ref")
    if skills_ref_bin:
        try:
            res = subprocess.run(
                [skills_ref_bin, "validate", str(skill_dir)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode != 0:
                errors.append(f"skills-ref validation failed: {res.stderr or res.stdout}")
        except Exception as exc:
            warnings.append(f"Could not execute skills-ref CLI: {exc}")

    return {
        "name": dir_name,
        "path": str(skill_md),
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "token_estimate": tier1_tokens + tier2_tokens,
        "lines_count": lines_count,
        "tier3_files": tier3_files,
        "metadata": metadata,
    }


def validate_all_skills(skills_dir: Path) -> dict[str, Any]:
    """Validate all skill packages in directory."""
    if not skills_dir.exists():
        return {
            "valid": False,
            "skills": [],
            "errors": [f"Skills directory does not exist: {skills_dir}"],
        }

    skill_dirs = [d for d in sorted(skills_dir.iterdir()) if d.is_dir()]
    if not skill_dirs:
        return {
            "valid": False,
            "skills": [],
            "errors": [f"No skill packages found in {skills_dir}"],
        }

    skills_results = []
    all_errors = []
    for s_dir in skill_dirs:
        res = validate_single_skill(s_dir)
        skills_results.append(res)
        if not res["valid"]:
            for err in res["errors"]:
                all_errors.append(f"[{res['name']}] {err}")

    return {
        "valid": len(all_errors) == 0,
        "skills": skills_results,
        "errors": all_errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate Agent Skills Packages (agentskills.io)")
    parser.add_argument("--path", type=str, default="", help="Path to skills directory")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    if args.path:
        skills_dir = Path(args.path)
    else:
        base_dir = Path(__file__).resolve().parent.parent
        skills_dir = base_dir / "skills"
        if not skills_dir.exists():
            skills_dir = Path("skills")
        if not skills_dir.exists():
            skills_dir = Path("backend/skills")

    results = validate_all_skills(skills_dir)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n=== Agent Skills Validation Report ===")
        print(f"Target Directory: {skills_dir.resolve()}\n")
        print(f"{'Skill Name':<25} {'Lines':<8} {'Tokens':<10} {'Tier 3 Files':<20} {'Status'}")
        print("-" * 75)
        for s in results["skills"]:
            status_str = "PASS" if s["valid"] else "FAIL"
            t3_summary = f"{len(s['tier3_files'])} file(s)"
            print(f"{s['name']:<25} {s['lines_count']:<8} {s['token_estimate']:<10} {t3_summary:<20} {status_str}")

        if results["errors"]:
            print("\nErrors Detected:")
            for err in results["errors"]:
                print(f"  ❌ {err}")
        else:
            print("\n✅ All skill packages conform to the agentskills.io specification!")

    sys.exit(0 if results["valid"] else 1)


if __name__ == "__main__":
    main()
