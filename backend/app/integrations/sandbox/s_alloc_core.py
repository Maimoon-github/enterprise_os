"""Deterministic Media & Budget Allocator Core for S_ALLOC (STRAT-03).

Provides constrained diminishing-returns / marginal-ROI allocation,
response curves, uncertainty weighting, channel min/max bounds,
unallocated contingency, and explicit model diagnostics.
"""

from __future__ import annotations

import json
from typing import Any


def _float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def execute_s_alloc(payload: dict[str, Any]) -> dict[str, str]:
    """S_ALLOC: Deterministic Media & Budget Allocator [Micro-Tool: Optimization Modeler].

    Applies deterministic, constrained, diminishing-returns / mROI allocation across
    omnichannel ad networks, models full-funnel stage distribution, compares alternative
    scenarios, and enforces strict financial budget caps and channel bounds.
    """
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    brand_id = str(payload.get("brand_id", "default"))
    time_horizon = str(payload.get("time_horizon", "90_days"))
    objective = str(payload.get("objective", "balanced omnichannel planning"))

    # 1. Budget Ceiling & Authorized Total
    raw_budget = payload.get("budget", payload.get("budget_cap", payload.get("budget_ceiling", 10000.0)))
    requested_budget = max(0.0, _float(raw_budget, 10000.0))
    raw_ceiling = payload.get("budget_ceiling")
    ceiling = max(0.0, _float(raw_ceiling, requested_budget))
    budget_total = min(requested_budget, ceiling)

    # 2. Channel Parsing and Normalization
    raw_channels = payload.get("channels", "meta,google,tiktok,linkedin")
    if isinstance(raw_channels, list):
        channels = [str(x).strip().lower() for x in raw_channels if str(x).strip()]
    else:
        channels = [x.strip().lower() for x in str(raw_channels).split(",") if x.strip()]
    if not channels:
        channels = ["meta", "google", "tiktok"]
    # Deduplicate preserving order
    channels = list(dict.fromkeys(channels))

    defaults = {
        "meta": 3.2,
        "google": 3.8,
        "tiktok": 2.6,
        "linkedin": 2.1,
        "youtube": 2.9,
        "email": 4.5,
    }

    media_history = _json(payload.get("media_history") or payload.get("performance_telemetry"), {})
    if not isinstance(media_history, dict):
        media_history = {}

    constraints = _json(payload.get("channel_constraints"), {})
    if not isinstance(constraints, dict):
        raw_c = _json(payload.get("constraints"), {})
        constraints = raw_c if isinstance(raw_c, dict) else {}

    incrementality = _json(payload.get("incrementality_evidence"), {})
    reasoning = _json(payload.get("s_alloc_reasoning"), {})

    # 3. Claims, Objections & Competitor Signals
    applied_claims: list[str] = []
    claims = _json(payload.get("t16_claims") or payload.get("approved_claims"), [])
    if isinstance(claims, list):
        for item in claims:
            if isinstance(item, dict):
                text = item.get("text") or item.get("claim_text") or item.get("id")
                if text:
                    applied_claims.append(str(text))
            elif item:
                applied_claims.append(str(item))

    addressed_objections: list[str] = []
    objections = _json(payload.get("t17_objections") or payload.get("objections"), [])
    if isinstance(objections, list):
        for item in objections:
            if isinstance(item, dict):
                text = item.get("theme") or item.get("objection_type") or item.get("objection_id")
                if text:
                    addressed_objections.append(str(text))
            elif item:
                addressed_objections.append(str(item))

    factored_competitor_signals: list[str] = []
    comp = _json(payload.get("t18_competitor") or payload.get("competitor_signals"), {})
    competitor_threat_elevated = False
    if isinstance(comp, dict) and comp:
        name = comp.get("competitor", "Competitor")
        threat = str(comp.get("threat_level", "medium")).lower()
        sig = f"{name} threat: {threat}"
        if comp.get("benchmark_price") is not None:
            sig += f", benchmark price: ${comp.get('benchmark_price')}"
        factored_competitor_signals.append(sig)
        competitor_threat_elevated = threat in {"high", "critical"} or comp.get("pricing_trajectory") == "discounting_aggressive"

    # 4. Priors, Saturation & Incrementality Calibration
    priors: dict[str, float] = {}
    uncertainty: dict[str, float] = {}
    saturation: dict[str, float] = {}
    reference_spend: dict[str, float] = {}
    evidence_factor: dict[str, float] = {c: 1.0 for c in channels}

    for ch in channels:
        hist = media_history.get(ch, {}) if isinstance(media_history.get(ch, {}), dict) else {}
        prior_val = payload.get(f"prior_roas_{ch}")
        if prior_val is None:
            prior_val = hist.get("roi") or hist.get("prior_roas") if isinstance(hist, dict) else None
        prior = _float(prior_val, defaults.get(ch, 2.5))
        priors[ch] = max(0.01, prior)

        sd_val = payload.get(f"prior_roas_sd_{ch}")
        if sd_val is None:
            sd_val = hist.get("roas_sd") if isinstance(hist, dict) else None
        uncertainty[ch] = max(0.0, _float(sd_val, prior * 0.25))

        reference_spend[ch] = max(0.0, _float(hist.get("spend"), budget_total / max(len(channels), 1)))

        sat_val = payload.get(f"saturation_spend_{ch}")
        if sat_val is None:
            sat_val = hist.get("saturation_spend") if isinstance(hist, dict) else None
        sat_default = max(reference_spend[ch], budget_total / max(len(channels), 1), 1.0)
        saturation[ch] = max(1.0, _float(sat_val, sat_default))

    # Evidence adjustments
    if applied_claims:
        if "meta" in evidence_factor:
            evidence_factor["meta"] *= 1.10
        if "tiktok" in evidence_factor:
            evidence_factor["tiktok"] *= 1.05
    if addressed_objections and "google" in evidence_factor:
        evidence_factor["google"] *= 1.15
    if competitor_threat_elevated and "google" in evidence_factor:
        evidence_factor["google"] *= 1.10

    # Incrementality calibration multiplier
    if isinstance(incrementality, dict):
        for ch, inc_data in incrementality.items():
            if ch in evidence_factor:
                if isinstance(inc_data, dict):
                    lift = _float(inc_data.get("lift_multiplier", inc_data.get("incrementality_factor", 1.0)), 1.0)
                    evidence_factor[ch] *= max(0.1, min(2.0, lift))
                elif isinstance(inc_data, (int, float)):
                    evidence_factor[ch] *= max(0.1, min(2.0, float(inc_data)))

    def response(ch: str, spend: float) -> float:
        """Saturating planning response proxy. This is not a fitted causal MMM."""
        return priors[ch] * evidence_factor[ch] * spend / (1.0 + spend / saturation[ch])

    def mroi(ch: str, spend: float) -> float:
        """Marginal return on ad spend derivative."""
        return priors[ch] * evidence_factor[ch] / ((1.0 + spend / saturation[ch]) ** 2)

    # 5. Channel Constraints: Min / Max bounds
    min_spend: dict[str, float] = {}
    max_spend: dict[str, float] = {}
    for ch in channels:
        c = constraints.get(ch, {}) if isinstance(constraints.get(ch, {}), dict) else {}
        mn = max(0.0, _float(c.get("min_spend"), 0.0))
        mx = max(0.0, _float(c.get("max_spend"), budget_total))
        if c.get("min_share") is not None:
            mn = max(mn, budget_total * max(0.0, min(1.0, _float(c.get("min_share"), 0.0))))
        if c.get("max_share") is not None:
            mx = min(mx, budget_total * max(0.0, min(1.0, _float(c.get("max_share"), 1.0))))
        max_spend[ch] = max(mn, mx)
        min_spend[ch] = min(mn, max_spend[ch])

    allocations = dict(min_spend)
    min_total = sum(allocations.values())
    warnings: list[str] = []
    if min_total > budget_total and min_total > 0:
        warnings.append("Channel minimums exceed the authorized budget; minimums were proportionally scaled to the ceiling.")
        scale = budget_total / min_total
        allocations = {ch: amount * scale for ch, amount in allocations.items()}

    # 6. Constrained Diminishing-Returns / mROI Iterative Allocation
    remaining = max(0.0, budget_total - sum(allocations.values()))
    quantum = max(budget_total / 200.0, 0.01) if budget_total else 0.0
    mroi_floor = _float(payload.get("mroi_floor"), 0.0)

    while remaining > 0.005 and quantum > 0:
        eligible = [
            ch for ch in channels
            if (allocations.get(ch, 0.0) + 0.005 <= max_spend[ch])
            and (mroi(ch, allocations.get(ch, 0.0)) >= mroi_floor)
        ]
        if not eligible:
            break
        ch = max(
            eligible,
            key=lambda c: max(0.01, mroi(c, allocations.get(c, 0.0)) - 0.25 * uncertainty[c]),
        )
        room = max_spend[ch] - allocations.get(ch, 0.0)
        delta = min(remaining, quantum, room)
        if delta <= 0:
            break
        allocations[ch] = allocations.get(ch, 0.0) + delta
        remaining -= delta

    allocations = {ch: round(allocations.get(ch, 0.0), 2) for ch in channels}
    allocated_total = round(sum(allocations.values()), 2)
    if allocated_total > budget_total and allocations:
        ch = max(allocations, key=lambda k: allocations[k])
        allocations[ch] = round(max(0.0, allocations[ch] - (allocated_total - budget_total)), 2)
        allocated_total = round(sum(allocations.values()), 2)

    def blended_roi(allocs: dict[str, float]) -> float:
        spend = sum(allocs.values())
        return 0.0 if spend <= 0 else sum(response(ch, amount) for ch, amount in allocs.items()) / spend

    expected_blended_roas = blended_roi(allocations)
    marginal = {ch: round(mroi(ch, allocations[ch]), 4) for ch in channels}

    # 7. Response Curves Sampling
    curves: dict[str, list[dict[str, float]]] = {}
    for ch in channels:
        top = max(max_spend[ch], allocations[ch], saturation[ch])
        points: list[dict[str, float]] = []
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            spend_pt = round(top * frac, 2)
            points.append({
                "spend": spend_pt,
                "expected_incremental_kpi": round(response(ch, spend_pt), 4),
                "mroi": round(mroi(ch, spend_pt), 4),
            })
        curves[ch] = points

    # 8. Channel Allocation Objects
    roles_map = {
        "meta": "Top-of-funnel acquisition, discovery, and dynamic retargeting",
        "google": "High-intent search capture and competitor brand defense",
        "tiktok": "Short-form video discovery and social proof",
        "linkedin": "B2B consideration, authority, and partner outreach",
        "youtube": "Mid-funnel video education and brand lift",
        "email": "Retention, lifecycle re-engagement, and repeat subscriptions",
    }
    channel_objs: list[dict[str, Any]] = []
    for ch in channels:
        pct = allocations[ch] / budget_total * 100 if budget_total else 0.0
        channel_objs.append({
            "channel": ch,
            "allocated_amount": allocations[ch],
            "percentage_of_total": round(pct, 1),
            "role": roles_map.get(ch, f"Omnichannel activation on {ch}"),
            "primary_kpi": "mROI / incremental KPI",
            "prior_roas": priors[ch],
            "target_roas_range": [round(max(0.0, priors[ch] - uncertainty[ch]), 2), round(priors[ch] + uncertainty[ch], 2)],
            "constraints": [
                f"min=${min_spend[ch]:.2f}",
                f"max=${max_spend[ch]:.2f}",
                f"saturation=${saturation[ch]:.2f}",
            ],
        })

    # 9. Funnel Stages Model
    tofu_pct, mofu_pct, bofu_pct, ret_pct = (0.40, 0.30, 0.20, 0.10) if addressed_objections else (0.45, 0.25, 0.20, 0.10)
    stage_pcts = [("TOFU", tofu_pct), ("MOFU", mofu_pct), ("BOFU", bofu_pct), ("RETENTION", ret_pct)]
    stage_amounts = {name: round(budget_total * pct, 2) for name, pct in stage_pcts}
    stage_amounts["RETENTION"] = round(max(0.0, budget_total - stage_amounts["TOFU"] - stage_amounts["MOFU"] - stage_amounts["BOFU"]), 2)

    stage_full_names = {
        "TOFU": "Top of Funnel (Awareness & Discovery)",
        "MOFU": "Middle of Funnel (Consideration & Education)",
        "BOFU": "Bottom of Funnel (Conversion & Intent Capture)",
        "RETENTION": "Retention & Lifecycle Re-engagement",
    }
    stage_targets = {
        "TOFU": {"cpm_target": "$12.50", "ctr_target": "1.8%", "thumbstop_rate": "32%"},
        "MOFU": {"page_dwell_time": "2m 15s", "content_engagement_rate": "4.2%"},
        "BOFU": {"conversion_rate": "3.5%", "target_cpa": "$28.00"},
        "RETENTION": {"repeat_purchase_rate": "24%", "ltv_30d": "$62.00"},
    }
    funnel: list[dict[str, Any]] = []
    mapping = {
        "TOFU": ["meta", "tiktok", "youtube"],
        "MOFU": ["meta", "youtube", "linkedin"],
        "BOFU": ["google", "meta"],
        "RETENTION": ["email", "meta"],
    }
    for name, pct in stage_pcts:
        chs = [c for c in channels if c in mapping[name]] or channels[:1]
        funnel.append({
            "stage": name,
            "stage_name": stage_full_names.get(name, name),
            "allocated_amount": stage_amounts[name],
            "percentage_of_total": round(pct * 100, 1),
            "channels": chs,
            "objective": {
                "TOFU": "Broad audience discovery, hook testing, and clinical claim demonstration",
                "MOFU": "Objection neutralization, product dossier transparency, and customer sentiment reinforcement",
                "BOFU": "High-intent search capture, competitor alternative conquesting, and checkout conversion",
                "RETENTION": "Customer onboarding, regimen adherence, and repeat replenishment subscriptions",
            }[name],
            "transition_hypothesis": {
                "TOFU": "Prospects exposed to verified claims and high-relevance video creative click through to educational landing pages.",
                "MOFU": f"Neutralize known customer objections ({', '.join(addressed_objections[:2]) if addressed_objections else 'price/quality'}) via clinical proof dossiers and peer reviews.",
                "BOFU": "Capture high-intent searchers seeking validated solutions, beating competitor discounting through verified claims superiority.",
                "RETENTION": "Delight verified buyers with tailored post-purchase education to accelerate repeat replenishment within 60 days.",
            }[name],
            "target_metrics": stage_targets.get(name, {}),
        })

    # 10. Alternative Scenarios
    def normalize(weights: dict[str, float]) -> dict[str, float]:
        total = sum(weights.values()) or 1.0
        return {c: round(budget_total * v / total, 2) for c, v in weights.items()}

    aggressive = normalize({c: allocations[c] * (1.25 if c in {"meta", "tiktok", "youtube"} else 0.75) for c in channels})
    conservative = normalize({c: allocations[c] * (1.35 if c in {"google", "email"} else 0.70) for c in channels})

    pref = str(reasoning.get("scenario_emphasis", "")).lower() if isinstance(reasoning, dict) else ""
    if pref not in {"balanced", "aggressive", "conservative"}:
        low = objective.lower()
        if any(x in low for x in ("efficiency", "profit", "roas", "margin")):
            pref = "conservative"
        elif any(x in low for x in ("awareness", "reach", "scale", "growth")):
            pref = "aggressive"
        else:
            pref = "balanced"
    rec_id = f"scenario_{pref}"

    scenarios = [
        {
            "scenario_id": "scenario_balanced",
            "scenario_name": "Balanced Omnichannel Growth",
            "description": "Marginal-return-aware constrained allocation balancing discovery with intent capture.",
            "is_recommended": rec_id == "scenario_balanced",
            "allocations_by_channel": allocations,
            "allocations_by_stage": stage_amounts,
            "expected_blended_roas": round(blended_roi(allocations), 2),
            "risk_level": "medium",
            "key_assumptions": ["Planning response curves are proxies unless calibrated by experiments or a fitted MMM."],
        },
        {
            "scenario_id": "scenario_aggressive",
            "scenario_name": "Aggressive Audience Scale",
            "description": "Tilts spend toward discovery/upper-funnel channels for rapid market penetration.",
            "is_recommended": rec_id == "scenario_aggressive",
            "allocations_by_channel": aggressive,
            "allocations_by_stage": {
                "TOFU": round(budget_total * 0.60, 2),
                "MOFU": round(budget_total * 0.20, 2),
                "BOFU": round(budget_total * 0.15, 2),
                "RETENTION": round(budget_total * 0.05, 2),
            },
            "expected_blended_roas": round(blended_roi(aggressive), 2),
            "risk_level": "high",
            "key_assumptions": ["Higher reach may encounter faster saturation and creative fatigue."],
        },
        {
            "scenario_id": "scenario_conservative",
            "scenario_name": "Conservative ROAS-First",
            "description": "Tilts spend toward high-intent conversion and customer retention.",
            "is_recommended": rec_id == "scenario_conservative",
            "allocations_by_channel": conservative,
            "allocations_by_stage": {
                "TOFU": round(budget_total * 0.30, 2),
                "MOFU": round(budget_total * 0.25, 2),
                "BOFU": round(budget_total * 0.30, 2),
                "RETENTION": round(budget_total * 0.15, 2),
            },
            "expected_blended_roas": round(blended_roi(conservative), 2),
            "risk_level": "low",
            "key_assumptions": ["Lower reach is acceptable in exchange for near-term capital efficiency."],
        },
    ]

    # 11. Explicit Model Health Diagnostics
    health_reasons = [
        "Current implementation is a deterministic response-curve planning proxy, not a fitted causal MMM."
    ]
    if not media_history:
        health_reasons.append("No media-history/performance series supplied.")
    if not incrementality:
        health_reasons.append("No incrementality calibration supplied.")

    health_status = "REVIEW"
    if budget_total <= 0 or not channels:
        health_status = "FAIL"
        health_reasons.append("Budget total is zero or channel set is empty.")

    model_diagnostics = {
        "measurement_mode": "deterministic_response_curve_proxy",
        "causal_mmm": False,
        "health_status": health_status,
        "health_reasons": health_reasons,
        "incrementality_calibrated": bool(incrementality),
        "marginal_roas": marginal,
        "warnings": warnings,
    }

    # 12. Assumptions, Caveats & Confidence
    conf = 0.65
    if applied_claims:
        conf += 0.05
    if addressed_objections:
        conf += 0.05
    if factored_competitor_signals:
        conf += 0.05
    if media_history:
        conf += 0.05
    if incrementality:
        conf += 0.05
    conf = min(0.85, conf)

    assumptions = [
        "Response curves use a saturating planning proxy and must not be represented as causal MMM estimates.",
        "All budget shifts are constrained by the authorized ceiling and channel bounds.",
    ]
    if isinstance(reasoning, dict):
        assumptions.extend(str(x) for x in reasoning.get("modeling_assumptions", []) if x)

    caveats = list(health_reasons) + [
        "Projected ROI/mROI values are planning estimates, not guaranteed financial results."
    ]
    constraints_text = [
        f"Total budget proposal strictly capped at authorized ceiling of ${ceiling:.2f}.",
        f"Channels restricted to: {', '.join(channels)}.",
        "No automated outbound campaign publishing or spend modification without explicit HITL sign-off.",
    ]

    # 13. Omnichannel Strategy Plan Assembly
    provenance_data: dict[str, Any] = {
        "modeled_by": "S_ALLOC",
        "task_id": task_id,
        "tenant_id": tenant_id,
        "model_diagnostics": model_diagnostics,
        "applied_evidence": {
            "t16_claims_count": len(applied_claims),
            "t17_objections_count": len(addressed_objections),
            "t18_competitor_signals_count": len(factored_competitor_signals),
        },
    }
    if reasoning:
        provenance_data["s_alloc_reasoning"] = {
            "scenario_emphasis": pref,
            "kpi_priorities": reasoning.get("kpi_priorities", []),
            "estimated_confidence": reasoning.get("estimated_confidence", 0.65),
        }

    plan = {
        "plan_id": f"strat-{task_id}",
        "tenant_id": tenant_id,
        "brand_id": brand_id,
        "time_horizon": time_horizon,
        "budget_ceiling": ceiling,
        "total_allocated": allocated_total,
        "unallocated_contingency": round(max(0.0, ceiling - allocated_total), 2),
        "channel_allocations": channel_objs,
        "funnel_stages": funnel,
        "scenarios": scenarios,
        "recommended_scenario": rec_id,
        "approved_claims_applied": applied_claims,
        "objections_addressed": addressed_objections,
        "competitor_signals_factored": factored_competitor_signals,
        "assumptions": assumptions,
        "constraints": constraints_text,
        "unsupported_estimates_or_caveats": caveats,
        "provenance": provenance_data,
        "confidence": {
            "point_estimate": round(conf, 2),
            "lower_bound": round(max(0.0, conf - 0.15), 2),
            "upper_bound": round(min(1.0, conf + 0.10), 2),
        },
    }

    primary = max(allocations, key=lambda k: allocations[k]) if allocations else "none"

    result: dict[str, str] = {
        "status": "success",
        "task_id": task_id,
        "budget_total": str(budget_total),
        "allocated_total": str(allocated_total),
        "allocations": json.dumps(allocations),
        "expected_blended_roas": f"{expected_blended_roas:.2f}",
        "primary_channel": primary,
        "marginal_roas": json.dumps(marginal),
        "response_curves": json.dumps(curves),
        "model_diagnostics": json.dumps(model_diagnostics),
        "funnel_model": json.dumps(funnel),
        "scenarios": json.dumps(scenarios),
        "strategy_plan": json.dumps(plan),
    }
    if reasoning:
        result["s_alloc_reasoning"] = json.dumps(reasoning)

    return result
