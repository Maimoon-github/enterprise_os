from typing import Any

BRAND_VOICE_REGISTRY: dict[str, dict[str, Any]] = {
    "default": {
        "voice": "Authoritative, insightful, data-driven, and forward-looking.",
        "banned_phrases": ["game-changer", "paradigm shift", "synergy", "disruptive"],
        "primary_pillars": ["Zero Hallucinations", "Deterministic State", "Human Governance"],
    },
    "apex-horizon": {
        "voice": "Authoritative, insightful, data-driven, with complete human governance and deterministic state.",
        "banned_phrases": ["game-changer", "paradigm shift", "synergy", "disruptive", "revolutionary", "deep dive"],
        "primary_pillars": ["Zero Hallucinations", "Deterministic State", "Human Governance", "Auditable Lineage"],
    },
}

PERSONA_REGISTRY: dict[str, dict[str, Any]] = {
    "b2b_exec": {
        "name": "B2B SaaS Executives",
        "pain_points": ["Runaway GenAI hallucinations", "Compliance risk", "Wasted ad budget"],
        "preferred_hooks": ["Risk mitigation", "Auditable agent governance", "Enterprise ROI"],
    },
    "growth_lead": {
        "name": "Growth & Performance Marketers",
        "pain_points": ["Multi-platform distribution friction", "Creative fatigue", "Manual scheduling"],
        "preferred_hooks": ["Autonomous multi-channel fan-out", "ReWOO anomaly loops", "Zero-prompt workflows"],
    },
    "platform_eng": {
        "name": "Platform & DevOps Engineers",
        "pain_points": ["Black-box agent systems", "Lack of state persistence", "Security leaks"],
        "preferred_hooks": ["Deterministic LangGraph checkpointers", "Rootless Podman sandbox", "W3C trace context"],
    },
}


def get_brand_voice_guidelines(brand_id: str) -> str:
    """Return comprehensive voice, tone, and compliance constraints for a brand."""
    data = BRAND_VOICE_REGISTRY.get(brand_id, BRAND_VOICE_REGISTRY["default"])
    pillars = ", ".join(data["primary_pillars"])
    banned = ", ".join(data["banned_phrases"])
    return (
        f"Brand Voice [{brand_id}]: {data['voice']}\n"
        f"Primary Value Pillars: {pillars}\n"
        f"Prohibited Phrases: {banned}"
    )


def get_persona_guidelines(segment_id: str) -> str:
    """Return target audience segment positioning and messaging hooks."""
    data = PERSONA_REGISTRY.get(segment_id, PERSONA_REGISTRY["b2b_exec"])
    pain_points = ", ".join(data["pain_points"])
    hooks = ", ".join(data["preferred_hooks"])
    return (
        f"Target Persona [{segment_id} - {data['name']}]:\n"
        f"Key Pain Points: {pain_points}\n"
        f"High-Converting Hooks: {hooks}"
    )


get_brand_guidelines = get_brand_voice_guidelines
