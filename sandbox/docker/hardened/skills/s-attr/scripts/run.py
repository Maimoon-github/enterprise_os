#!/usr/bin/env python3
"""S_ATTR Attribution & Decay Modeler Execution Script."""
import json
import math
import sys

def run_s_attr(payload: dict) -> dict:
    task_id = payload.get("task_id", "unknown")
    try:
        reported_roas = float(payload.get("roas", payload.get("metrics_roas", "3.4")))
    except (ValueError, TypeError):
        reported_roas = 3.4

    try:
        days_active = float(payload.get("days_active", "14.0"))
        if days_active < 0:
            days_active = 0.0
    except (ValueError, TypeError):
        days_active = 14.0

    decay_rate = 0.05
    decay_multiplier = math.exp(-decay_rate * days_active)
    projected_roas = reported_roas * decay_multiplier

    fatigue_detected = decay_multiplier < 0.65
    recommended_action = "refresh_creative_hooks" if fatigue_detected else "scale_spend"

    delta_statement = (
        f"Creative fatigue at {decay_multiplier:.2f} after {days_active:.0f} days. "
        f"Current ROAS {reported_roas:.2f}, projected {projected_roas:.2f}. "
        f"Recommendation: {recommended_action}."
    )

    return {
        "status": "success",
        "task_id": task_id,
        "decay_multiplier": f"{decay_multiplier:.2f}",
        "projected_roas": f"{projected_roas:.2f}",
        "fatigue_detected": str(fatigue_detected),
        "recommended_action": recommended_action,
        "learning_delta": delta_statement,
        "confidence": "0.85",
    }

if __name__ == "__main__":
    raw_input = sys.stdin.read()
    data = json.loads(raw_input) if raw_input.strip() else {}
    result = run_s_attr(data)
    sys.stdout.write(json.dumps(result))
