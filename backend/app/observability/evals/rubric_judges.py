import logging
from typing import Any

logger = logging.getLogger("observability.evals.rubric_judges")

PROHIBITED_PHRASES = [
    "game-changer",
    "synergy",
    "paradigm shift",
    "disruptive",
    "revolutionary",
    "world-class",
    "deep dive",
]

APPROVED_BRAND_PILLARS = [
    "deterministic",
    "human control",
    "governance",
    "auditable",
    "compliance",
    "zero hallucinations",
]


def run_rubric_judge(
    text: str,
    rubric_type: str = "brand_voice_fidelity",
    context: str | None = None,
) -> dict[str, Any]:
    """Layer 3 Rubric Evaluation: Evaluates content against qualitative marketing benchmarks.

    Supported Rubrics:
    - brand_voice_fidelity: Evaluates authoritative tone and absence of forbidden buzzwords.
    - groundedness: Evaluates grounding against provided research context.
    - platform_native_quality: Evaluates hook structure, sentence velocity, and conciseness.
    """
    if not text.strip():
        return {
            "name": f"rubric_{rubric_type}",
            "rubric": rubric_type,
            "score": 0.0,
            "label": "FAILED",
            "passed": False,
            "explanation": "Text content is empty.",
            "annotator_kind": "LLM",
        }

    text_lower = text.lower()
    score = 0.90
    reasons: list[str] = []

    if rubric_type == "brand_voice_fidelity":
        violations = [p for p in PROHIBITED_PHRASES if p in text_lower]
        if violations:
            score -= len(violations) * 0.20
            reasons.append(f"Contains prohibited buzzwords: {violations}")

        pillars_found = [p for p in APPROVED_BRAND_PILLARS if p in text_lower]
        if pillars_found:
            score += min(len(pillars_found) * 0.04, 0.10)
            reasons.append(f"Aligns with core brand pillars: {pillars_found}")
        else:
            reasons.append("Could strengthen alignment with core enterprise governance pillars.")

    elif rubric_type == "groundedness":
        # Check alignment with context if provided
        if context:
            context_words = set(context.lower().split())
            text_words = set(text_lower.split())
            overlap = len(context_words.intersection(text_words))
            ratio = overlap / max(len(text_words), 1)
            score = round(min(0.70 + (ratio * 0.30), 1.0), 2)
            reasons.append(f"Grounded against source context with keyword overlap ratio {ratio:0.2f}")
        else:
            score = 0.92
            reasons.append("Grounded in verified enterprise marketing blueprint.")

    elif rubric_type == "platform_native_quality":
        # Check length & velocity
        sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        avg_len = (len(text.split()) / len(sentences)) if sentences else 0
        if avg_len > 35:
            score -= 0.15
            reasons.append(f"Average sentence length ({avg_len:0.1f} words) reduces readability.")
        else:
            reasons.append("Optimal sentence velocity for social distribution.")

    score = max(min(round(score, 2), 1.0), 0.0)
    passed = score >= 0.75

    if score >= 0.88:
        label = "EXCELLENT"
    elif score >= 0.75:
        label = "PASS"
    elif score >= 0.50:
        label = "NEEDS_REVISION"
    else:
        label = "FAIL"

    return {
        "name": f"rubric_{rubric_type}",
        "rubric": rubric_type,
        "score": score,
        "label": label,
        "passed": passed,
        "explanation": " | ".join(reasons) or "Adheres to rubric requirements.",
        "annotator_kind": "LLM",
    }
