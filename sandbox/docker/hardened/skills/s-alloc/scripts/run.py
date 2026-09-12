#!/usr/bin/env python3
"""S_ALLOC Optimization Modeler Execution Script."""
import json
import sys

def run_s_alloc(payload: dict) -> dict:
    task_id = payload.get("task_id", "unknown")
    try:
        budget_total = float(payload.get("budget", payload.get("budget_cap", "10000.0")))
        if budget_total < 0:
            budget_total = 0.0
    except (ValueError, TypeError):
        budget_total = 10000.0

    channels_raw = payload.get("channels", "meta,google,tiktok,linkedin")
    channels = [c.strip() for c in channels_raw.split(",") if c.strip()]
    if not channels:
        channels = ["meta", "google", "tiktok"]

    roas_priors = {
        "meta": float(payload.get("prior_roas_meta", "3.2")),
        "google": float(payload.get("prior_roas_google", "3.8")),
        "tiktok": float(payload.get("prior_roas_tiktok", "2.6")),
        "linkedin": float(payload.get("prior_roas_linkedin", "2.1")),
    }

    channel_weights = {c: roas_priors.get(c, 2.5) for c in channels}
    sum_weights = sum(channel_weights.values()) or 1.0

    allocations = {}
    expected_blended_roas = 0.0
    for ch in channels:
        share = channel_weights[ch] / sum_weights
        amount = round(budget_total * share, 2)
        allocations[ch] = amount
        expected_blended_roas += share * channel_weights[ch]

    return {
        "status": "success",
        "task_id": task_id,
        "budget_total": str(budget_total),
        "allocations": json.dumps(allocations),
        "expected_blended_roas": f"{expected_blended_roas:.2f}",
        "primary_channel": max(allocations, key=allocations.get) if allocations else "none",
    }

if __name__ == "__main__":
    raw_input = sys.stdin.read()
    data = json.loads(raw_input) if raw_input.strip() else {}
    result = run_s_alloc(data)
    sys.stdout.write(json.dumps(result))
