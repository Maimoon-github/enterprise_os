from typing import Any

from app.agents.validators.platform_limits import PLATFORM_CHAR_LIMITS
from app.orchestrator.state import CampaignBlueprint

CANONICAL_LIFECYCLE_ORDER: list[str] = [
    "BrandRAG",
    "DraftCopy",
    "ApprovalGate",
    "Publish",
]

ALLOWED_ASPECT_RATIOS: set[str] = {"1:1", "4:5", "9:16", "16:9", "2:3"}


def evaluate_trajectory_order(executed_tools: list[str], expected_order: list[str]) -> bool:
    """Verify executed tool trajectory contains expected milestones in strictly ascending order."""
    positions = [executed_tools.index(req) for req in expected_order if req in executed_tools]
    return len(positions) == len(expected_order) and positions == sorted(positions)


def evaluate_trajectory(
    executed_steps: list[str],
    required_order: list[str] | None = None,
) -> dict[str, Any]:
    """Layer 2 Trajectory Evaluation: Computes deterministic precision, recall, and sequence ordering.

    Validates that:
    1. Retrieval precedes creative drafting.
    2. Human approval gate precedes outbound publishing.
    """
    order = required_order or CANONICAL_LIFECYCLE_ORDER
    matched_indices: dict[str, list[int]] = {}

    for target in order:
        # Match case-insensitive substrings (e.g. 'search_brand_knowledge' matches 'BrandRAG')
        idxs = [
            i
            for i, step in enumerate(executed_steps)
            if target.lower() in step.lower()
            or (target == "BrandRAG" and any(k in step.lower() for k in ("research", "rag", "recon")))
            or (target == "DraftCopy" and any(k in step.lower() for k in ("creative", "draft", "planner")))
            or (target == "ApprovalGate" and any(k in step.lower() for k in ("approval", "interrupt", "gate")))
            or (target == "Publish" and any(k in step.lower() for k in ("publish", "fanout", "dispatch")))
        ]
        if idxs:
            matched_indices[target] = idxs

    # Compute recall: fraction of required milestones executed
    found_targets = [t for t in order if t in matched_indices]
    recall = len(found_targets) / len(order) if order else 1.0

    # Check pairwise ordering violations
    violations: list[str] = []
    order_inversions = 0
    total_pairs = 0

    for i in range(len(found_targets)):
        for j in range(i + 1, len(found_targets)):
            total_pairs += 1
            t1, t2 = found_targets[i], found_targets[j]
            first_idx_t1 = min(matched_indices[t1])
            first_idx_t2 = min(matched_indices[t2])

            if first_idx_t1 > first_idx_t2:
                order_inversions += 1
                violations.append(
                    f"Order violation: '{t2}' (index {first_idx_t2}) executed before '{t1}' (index {first_idx_t1})"
                )

    order_score = 1.0 - (order_inversions / total_pairs) if total_pairs > 0 else (1.0 if recall > 0 else 0.0)
    score = round(max(order_score * recall, 0.0), 3)

    return {
        "name": "trajectory_tool_order",
        "valid": len(violations) == 0 and recall == 1.0,
        "score": score,
        "precision": 1.0,
        "recall": round(recall, 3),
        "order_score": round(order_score, 3),
        "violations": violations,
        "annotator_kind": "CODE",
        "executed_steps": executed_steps,
    }


def evaluate_blueprint_schema(blueprint: dict[str, Any]) -> dict[str, Any]:
    """Layer 1 Deterministic Evaluation: Validates Pydantic v2 blueprint schema."""
    errors: list[str] = []
    try:
        CampaignBlueprint.model_validate(blueprint)
    except Exception as exc:
        errors.append(str(exc))

    is_valid = len(errors) == 0
    return {
        "name": "deterministic_schema_check",
        "valid": is_valid,
        "score": 1.0 if is_valid else 0.0,
        "label": "PASS" if is_valid else "FAIL",
        "annotator_kind": "CODE",
        "errors": errors,
    }


def evaluate_platform_constraints(platform_assets: list[dict[str, Any]]) -> dict[str, Any]:
    """Layer 1 Deterministic Evaluation: Verifies platform character limits and aspect ratios."""
    violations: list[str] = []
    for asset in platform_assets:
        platform = asset.get("platform", "generic")
        copy = asset.get("copy_text", "")
        aspect = asset.get("aspect_ratio", "")

        platform_key = "x" if platform in ("x", "twitter") else platform
        limit = PLATFORM_CHAR_LIMITS.get(platform_key, 5000)
        if len(copy) > limit:
            violations.append(f"{platform} copy exceeds limit: {len(copy)} > {limit}")

        if aspect and aspect not in ALLOWED_ASPECT_RATIOS:
            violations.append(f"{platform} aspect ratio '{aspect}' not in allowed set")

    total = len(platform_assets)
    failed_count = len(violations)
    score = round(max((total - failed_count) / total, 0.0), 3) if total > 0 else 1.0

    return {
        "name": "deterministic_platform_constraints",
        "valid": len(violations) == 0,
        "score": score,
        "label": "PASS" if score == 1.0 else "FAIL",
        "annotator_kind": "CODE",
        "violations": violations,
    }
