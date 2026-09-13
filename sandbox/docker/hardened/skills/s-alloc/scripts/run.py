#!/usr/bin/env python3
"""S_ALLOC Optimization Modeler Execution Script."""
import json
import sys

def run_s_alloc(payload: dict) -> dict:
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    brand_id = str(payload.get("brand_id", "default"))
    time_horizon = str(payload.get("time_horizon", "90_days"))

    # 1. Budget Ceiling & Requested Total
    raw_budget = payload.get("budget", payload.get("budget_cap", "10000.0"))
    try:
        budget_total = float(raw_budget)
        if budget_total < 0:
            budget_total = 0.0
    except (ValueError, TypeError):
        budget_total = 10000.0

    raw_ceiling = payload.get("budget_ceiling")
    if raw_ceiling is not None:
        try:
            budget_ceiling = float(raw_ceiling)
            if budget_ceiling >= 0:
                budget_total = min(budget_total, budget_ceiling)
        except (ValueError, TypeError):
            budget_ceiling = budget_total
    else:
        budget_ceiling = budget_total

    # 2. Channels Parsing
    channels_raw = payload.get("channels", "meta,google,tiktok,linkedin")
    if isinstance(channels_raw, list):
        channels = [str(c).strip().lower() for c in channels_raw if str(c).strip()]
    else:
        channels = [c.strip().lower() for c in str(channels_raw).split(",") if c.strip()]
    if not channels:
        channels = ["meta", "google", "tiktok"]

    seen = set()
    channels = [c for c in channels if not (c in seen or seen.add(c))]

    # 3. Target ROAS priors per channel
    default_priors = {
        "meta": 3.2,
        "google": 3.8,
        "tiktok": 2.6,
        "linkedin": 2.1,
        "youtube": 2.9,
        "email": 4.5,
    }

    roas_priors = {}
    for ch in channels:
        prior_key = f"prior_roas_{ch}"
        if prior_key in payload:
            try:
                roas_priors[ch] = float(payload[prior_key])
            except (ValueError, TypeError):
                roas_priors[ch] = default_priors.get(ch, 2.5)
        else:
            roas_priors[ch] = default_priors.get(ch, 2.5)

    # 4. Ingest and factor T16, T17, T18 signals
    applied_claims = []
    t16_raw = payload.get("t16_claims") or payload.get("approved_claims")
    if t16_raw:
        try:
            parsed_t16 = json.loads(t16_raw) if isinstance(t16_raw, str) else t16_raw
            if isinstance(parsed_t16, list):
                for item in parsed_t16:
                    if isinstance(item, dict):
                        applied_claims.append(str(item.get("text", item.get("claim_text", item.get("id", "")))))
                    else:
                        applied_claims.append(str(item))
            elif isinstance(parsed_t16, dict):
                applied_claims.append(str(parsed_t16.get("claim", "")))
        except Exception:
            applied_claims.append(str(t16_raw))

    addressed_objections = []
    t17_raw = payload.get("t17_objections") or payload.get("objections")
    if t17_raw:
        try:
            parsed_t17 = json.loads(t17_raw) if isinstance(t17_raw, str) else t17_raw
            if isinstance(parsed_t17, list):
                for item in parsed_t17:
                    if isinstance(item, dict):
                        addressed_objections.append(str(item.get("theme", item.get("objection_type", item.get("objection_id", "")))))
                    else:
                        addressed_objections.append(str(item))
        except Exception:
            addressed_objections.append(str(t17_raw))

    factored_competitor_signals = []
    t18_raw = payload.get("t18_competitor") or payload.get("competitor_signals")
    competitor_threat_elevated = False
    if t18_raw:
        try:
            parsed_t18 = json.loads(t18_raw) if isinstance(t18_raw, str) else t18_raw
            if isinstance(parsed_t18, dict):
                comp_name = parsed_t18.get("competitor", "Competitor")
                threat = parsed_t18.get("threat_level", "medium")
                price = parsed_t18.get("benchmark_price")
                active_ads = parsed_t18.get("active_ads")
                sig = f"{comp_name} threat: {threat}"
                if price:
                    sig += f", benchmark price: ${price}"
                if active_ads:
                    sig += f", active ads: {active_ads}"
                factored_competitor_signals.append(sig)
                if threat in ("high", "critical") or parsed_t18.get("pricing_trajectory") == "discounting_aggressive":
                    competitor_threat_elevated = True
            elif isinstance(parsed_t18, list):
                for item in parsed_t18:
                    factored_competitor_signals.append(str(item))
        except Exception:
            factored_competitor_signals.append(str(t18_raw))

    channel_weights = dict(roas_priors)
    if applied_claims and ("meta" in channel_weights or "tiktok" in channel_weights):
        if "meta" in channel_weights:
            channel_weights["meta"] *= 1.10
        if "tiktok" in channel_weights:
            channel_weights["tiktok"] *= 1.05

    if addressed_objections and "google" in channel_weights:
        channel_weights["google"] *= 1.15

    if competitor_threat_elevated and "google" in channel_weights:
        channel_weights["google"] *= 1.10

    # 5. Calculate Channel Allocations (Scenario: Balanced)
    sum_weights = sum(channel_weights.values()) or 1.0
    allocations = {}
    channel_alloc_objs = []
    expected_blended_roas = 0.0

    roles_map = {
        "meta": "Top-of-funnel customer acquisition, viral discovery, and dynamic retargeting",
        "google": "High-intent search capture, shopping intent, and competitor brand defense",
        "tiktok": "Youth demographic discovery, short-form video engagement, and social proof",
        "linkedin": "B2B authority, professional buyer consideration, and partner outreach",
        "youtube": "Mid-funnel video education, deep-dive product demonstrations, and brand lift",
        "email": "Retention, lifecycle re-engagement, and repeat customer monetization",
    }

    running_total = 0.0
    for idx, ch in enumerate(channels):
        share = channel_weights[ch] / sum_weights
        if idx == len(channels) - 1:
            amount = round(budget_total - running_total, 2)
            if amount < 0:
                amount = 0.0
        else:
            amount = round(budget_total * share, 2)
            running_total += amount

        allocations[ch] = amount
        expected_blended_roas += (channel_weights[ch] / sum_weights) * roas_priors.get(ch, 2.5)

        ch_role = roles_map.get(ch, f"Omnichannel activation on {ch}")
        prior_r = roas_priors.get(ch, 2.5)
        channel_alloc_objs.append({
            "channel": ch,
            "allocated_amount": amount,
            "percentage_of_total": round((amount / budget_total * 100) if budget_total > 0 else 0.0, 1),
            "role": ch_role,
            "primary_kpi": "CPA & Blended ROAS" if ch in ("meta", "google") else "Engagement & CTR",
            "prior_roas": prior_r,
            "target_roas_range": [round(prior_r * 0.85, 2), round(prior_r * 1.25, 2)],
            "constraints": [f"Channel budget capped at {amount:.2f}"],
        })

    allocated_total = round(sum(allocations.values()), 2)
    if allocated_total > budget_total and allocations:
        max_ch = max(allocations, key=allocations.get)
        allocations[max_ch] = round(allocations[max_ch] - (allocated_total - budget_total), 2)
        allocated_total = round(sum(allocations.values()), 2)

    # 6. Model Funnel Stages (TOFU, MOFU, BOFU, RETENTION)
    tofu_pct = 0.45 if not addressed_objections else 0.40
    mofu_pct = 0.25 if not addressed_objections else 0.30
    bofu_pct = 0.20
    ret_pct = 0.10

    tofu_amt = round(budget_total * tofu_pct, 2)
    mofu_amt = round(budget_total * mofu_pct, 2)
    bofu_amt = round(budget_total * bofu_pct, 2)
    ret_amt = round(budget_total - (tofu_amt + mofu_amt + bofu_amt), 2)
    if ret_amt < 0:
        ret_amt = 0.0

    tofu_channels = [c for c in channels if c in ("meta", "tiktok", "youtube")] or channels[:1]
    mofu_channels = [c for c in channels if c in ("meta", "youtube", "linkedin")] or channels[:2]
    bofu_channels = [c for c in channels if c in ("google", "meta")] or channels[-1:]
    ret_channels = [c for c in channels if c in ("email", "meta")] or ["email"]

    funnel_stage_objs = [
        {
            "stage": "TOFU",
            "stage_name": "Top of Funnel (Awareness & Discovery)",
            "allocated_amount": tofu_amt,
            "percentage_of_total": round(tofu_pct * 100, 1),
            "channels": tofu_channels,
            "objective": "Broad audience discovery, hook testing, and clinical claim demonstration",
            "transition_hypothesis": "Prospects exposed to verified claims and high-relevance video creative click through to educational landing pages.",
            "target_metrics": {"cpm_target": "$12.50", "ctr_target": "1.8%", "thumbstop_rate": "32%"},
        },
        {
            "stage": "MOFU",
            "stage_name": "Middle of Funnel (Consideration & Education)",
            "allocated_amount": mofu_amt,
            "percentage_of_total": round(mofu_pct * 100, 1),
            "channels": mofu_channels,
            "objective": "Objection neutralization, product dossier transparency, and customer sentiment reinforcement",
            "transition_hypothesis": f"Neutralize known customer objections ({', '.join(addressed_objections[:2]) if addressed_objections else 'price/quality'}) via clinical proof dossiers and peer reviews.",
            "target_metrics": {"page_dwell_time": "2m 15s", "content_engagement_rate": "4.2%"},
        },
        {
            "stage": "BOFU",
            "stage_name": "Bottom of Funnel (Conversion & Intent Capture)",
            "allocated_amount": bofu_amt,
            "percentage_of_total": round(bofu_pct * 100, 1),
            "channels": bofu_channels,
            "objective": "High-intent search capture, competitor alternative conquesting, and checkout conversion",
            "transition_hypothesis": "Capture high-intent searchers seeking validated solutions, beating competitor discounting through verified claims superiority.",
            "target_metrics": {"conversion_rate": "3.5%", "target_cpa": "$28.00"},
        },
        {
            "stage": "RETENTION",
            "stage_name": "Retention & Lifecycle Re-engagement",
            "allocated_amount": ret_amt,
            "percentage_of_total": round(ret_pct * 100, 1),
            "channels": ret_channels,
            "objective": "Customer onboarding, regimen adherence, and repeat replenishment subscriptions",
            "transition_hypothesis": "Delight verified buyers with tailored post-purchase education to accelerate repeat replenishment within 60 days.",
            "target_metrics": {"repeat_purchase_rate": "24%", "ltv_30d": "$62.00"},
        },
    ]

    # 7. Model Alternative Scenarios
    scenario_balanced = {
        "scenario_id": "scenario_balanced",
        "scenario_name": "Balanced Omnichannel Growth",
        "description": "Optimal risk-adjusted budget distribution balancing top-of-funnel acquisition with high-intent search capture and customer retention.",
        "is_recommended": True,
        "allocations_by_channel": dict(allocations),
        "allocations_by_stage": {"TOFU": tofu_amt, "MOFU": mofu_amt, "BOFU": bofu_amt, "RETENTION": ret_amt},
        "expected_blended_roas": round(expected_blended_roas, 2),
        "risk_level": "medium",
        "key_assumptions": [
            "Current channel auction CPMs remain stable within 15% quarterly variance.",
            "Landing page conversion infrastructure maintains 99.9% uptime.",
        ],
    }

    agg_allocs = {}
    for ch in channels:
        if ch in ("tiktok", "meta"):
            agg_allocs[ch] = round(allocations[ch] * 1.25, 2)
        else:
            agg_allocs[ch] = round(allocations[ch] * 0.75, 2)
    agg_sum = sum(agg_allocs.values()) or 1.0
    agg_allocs = {c: round(budget_total * (v / agg_sum), 2) for c, v in agg_allocs.items()}
    scenario_aggressive = {
        "scenario_id": "scenario_aggressive",
        "scenario_name": "Aggressive Audience Scale",
        "description": "Maximizes top-of-funnel reach and market penetration on high-volume discovery channels. Higher CAC volatility.",
        "is_recommended": False,
        "allocations_by_channel": agg_allocs,
        "allocations_by_stage": {
            "TOFU": round(budget_total * 0.60, 2),
            "MOFU": round(budget_total * 0.20, 2),
            "BOFU": round(budget_total * 0.15, 2),
            "RETENTION": round(budget_total * 0.05, 2),
        },
        "expected_blended_roas": round(expected_blended_roas * 0.88, 2),
        "risk_level": "high",
        "key_assumptions": [
            "Creative asset refresh cycle under 7 days to mitigate rapid ad fatigue.",
            "Higher willingness to tolerate customer acquisition cost variance during rapid scale.",
        ],
    }

    cons_allocs = {}
    for ch in channels:
        if ch in ("google", "email"):
            cons_allocs[ch] = round(allocations[ch] * 1.35, 2)
        else:
            cons_allocs[ch] = round(allocations[ch] * 0.70, 2)
    cons_sum = sum(cons_allocs.values()) or 1.0
    cons_allocs = {c: round(budget_total * (v / cons_sum), 2) for c, v in cons_allocs.items()}
    scenario_conservative = {
        "scenario_id": "scenario_conservative",
        "scenario_name": "Conservative ROAS-First",
        "description": "Prioritizes high-intent search capture and customer retention for immediate capital efficiency and risk minimization.",
        "is_recommended": False,
        "allocations_by_channel": cons_allocs,
        "allocations_by_stage": {
            "TOFU": round(budget_total * 0.30, 2),
            "MOFU": round(budget_total * 0.25, 2),
            "BOFU": round(budget_total * 0.30, 2),
            "RETENTION": round(budget_total * 0.15, 2),
        },
        "expected_blended_roas": round(expected_blended_roas * 1.12, 2),
        "risk_level": "low",
        "key_assumptions": [
            "Existing brand search volume is sufficient to absorb allocated budget without high CPC inflation.",
            "Lower net reach acceptable in exchange for immediate profitability.",
        ],
    }

    scenarios = [scenario_balanced, scenario_aggressive, scenario_conservative]

    assumptions = [
        "Historical channel prior ROAS figures reflect normalized non-promotional baseline performance.",
        "Conversion funnel assumes standard attribution window of 7-day click / 1-day view.",
        "Landing page assets and product specifications remain synchronized with approved compliance dossier.",
    ]

    constraints = [
        f"Total budget proposal strictly capped at authorized ceiling of ${budget_ceiling:.2f}.",
        f"Channel allocations restricted to approved tenant domain scope: {', '.join(channels)}.",
        "No automated outbound campaign publishing or spend modification without explicit HITL sign-off.",
    ]

    caveats = [
        "Projected blended ROAS and CPA ranges are mathematical optimization model estimates based on prior benchmarks, not guaranteed financial results.",
        "Aggressive top-of-funnel scale is sensitive to creative fatigue and market audience saturation.",
        "Competitor promotional pricing shifts may require dynamic reallocation of bottom-of-funnel conquesting budget.",
    ]

    plan_dict = {
        "plan_id": f"strat-{task_id}",
        "tenant_id": tenant_id,
        "brand_id": brand_id,
        "time_horizon": time_horizon,
        "budget_ceiling": budget_ceiling,
        "total_allocated": allocated_total,
        "unallocated_contingency": round(budget_ceiling - allocated_total, 2) if budget_ceiling >= allocated_total else 0.0,
        "channel_allocations": channel_alloc_objs,
        "funnel_stages": funnel_stage_objs,
        "scenarios": scenarios,
        "recommended_scenario": "scenario_balanced",
        "approved_claims_applied": applied_claims,
        "objections_addressed": addressed_objections,
        "competitor_signals_factored": factored_competitor_signals,
        "assumptions": assumptions,
        "constraints": constraints,
        "unsupported_estimates_or_caveats": caveats,
        "provenance": {
            "modeled_by": "S_ALLOC",
            "task_id": task_id,
            "tenant_id": tenant_id,
            "applied_evidence": {
                "t16_claims_count": len(applied_claims),
                "t17_objections_count": len(addressed_objections),
                "t18_competitor_signals_count": len(factored_competitor_signals),
            },
        },
        "confidence": {
            "point_estimate": 0.85,
            "lower_bound": 0.72,
            "upper_bound": 0.94,
        },
    }

    primary_ch = max(allocations, key=allocations.get) if allocations else "none"

    return {
        "status": "success",
        "task_id": task_id,
        "budget_total": str(budget_total),
        "allocated_total": str(allocated_total),
        "allocations": json.dumps(allocations),
        "expected_blended_roas": f"{expected_blended_roas:.2f}",
        "primary_channel": primary_ch,
        "funnel_model": json.dumps(funnel_stage_objs),
        "scenarios": json.dumps(scenarios),
        "strategy_plan": json.dumps(plan_dict),
    }

if __name__ == "__main__":
    raw_input = sys.stdin.read()
    data = json.loads(raw_input) if raw_input.strip() else {}
    result = run_s_alloc(data)
    sys.stdout.write(json.dumps(result))
