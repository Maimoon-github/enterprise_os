"""Deterministic Media & Budget Allocator Core for S_ALLOC (L6-02).

Sole canonical numerical implementation for:
- media_mix_modeler: concave response curve evaluation and marginal derivative
- budget_allocator_tool: constrained diminishing-returns / mROI optimization
- funnel_simulator: stage decomposition over allocated spend
- simulate_scenarios: multi-scenario analysis under authoritative constraints
- calculate_roas: blended and incremental ROAS calculations

Zero duplicated math. Strict constraint enforcement. Exact currency quantization.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from app.schemas.strategy import SAllocDomainStatus
else:
    try:
        from app.schemas.strategy import SAllocDomainStatus
    except ImportError:
        from enum import StrEnum

        class SAllocDomainStatus(StrEnum):
            OK = "OK"
            EVIDENCE_GAP = "EVIDENCE_GAP"
            INVALID_INPUT = "INVALID_INPUT"
            INFEASIBLE = "INFEASIBLE"
            UNSUPPORTED_MODEL = "UNSUPPORTED_MODEL"
            UNSUPPORTED_CONSTRAINT = "UNSUPPORTED_CONSTRAINT"
            SOLVER_FAILED = "SOLVER_FAILED"


# =============================================================================
# 1. Supported Concave Response Model
# =============================================================================


def model_media_mix(
    channel: str,
    spend: float,
    initial_marginal_return: float,
    saturation_spend: float,
) -> tuple[float, float, float]:
    """Evaluate deterministic response curve: R(x) = a*x / (1 + x/s).

    Parameters:
        channel: Channel identifier.
        spend: Non-negative spend amount x >= 0.
        initial_marginal_return: Initial marginal return a >= 0 (slope at x=0).
        saturation_spend: Saturation scale parameter s > 0.

    Returns:
        tuple (response, marginal_roas, second_derivative)
    """
    if spend < 0.0 or not math.isfinite(spend):
        raise ValueError(f"Spend must be a finite non-negative number for '{channel}': {spend}")
    if initial_marginal_return < 0.0 or not math.isfinite(initial_marginal_return):
        raise ValueError(
            f"initial_marginal_return must be finite and >= 0 for '{channel}': {initial_marginal_return}"
        )
    if saturation_spend <= 0.0 or not math.isfinite(saturation_spend):
        raise ValueError(
            f"saturation_spend must be finite and > 0 for '{channel}': {saturation_spend}"
        )

    denom = 1.0 + spend / saturation_spend
    response = (initial_marginal_return * spend) / denom
    marginal = initial_marginal_return / (denom * denom)
    second_derivative = -2.0 * initial_marginal_return / (saturation_spend * (denom**3))
    return response, marginal, second_derivative


def finite_incremental_gain(
    initial_marginal_return: float,
    saturation_spend: float,
    spend: float,
    quantum: float,
) -> float:
    """Exact finite difference incremental gain: R(x + q) - R(x)."""
    if initial_marginal_return <= 0.0 or quantum <= 0.0:
        return 0.0
    d1 = 1.0 + spend / saturation_spend
    d2 = 1.0 + (spend + quantum) / saturation_spend
    return (initial_marginal_return * quantum) / (d1 * d2)


def calculate_roas(
    allocations: dict[str, float],
    initial_marginal_returns: dict[str, float],
    saturation_spends: dict[str, float],
) -> float:
    """Compute modeled blended ROAS across channel spend allocations."""
    total_spend = sum(allocations.values())
    if total_spend <= 0.0:
        return 0.0
    total_response = 0.0
    for ch, spend in allocations.items():
        if spend > 0.0 and ch in initial_marginal_returns and ch in saturation_spends:
            resp, _, _ = model_media_mix(
                ch, spend, initial_marginal_returns[ch], saturation_spends[ch]
            )
            total_response += resp
    return total_response / total_spend


# =============================================================================
# 2. Constrained Diminishing-Returns Optimizer
# =============================================================================


def optimize_budget(
    budget: float,
    channels: list[str],
    min_spend: dict[str, float] | None = None,
    max_spend: dict[str, float] | None = None,
    initial_slopes: dict[str, float] | None = None,
    saturation_spends: dict[str, float] | None = None,
    mroi_floor: float = 0.0,
    currency_precision: int = 2,
    fixed_total: bool = False,
    max_iterations: int = 200,
    tolerance: float = 1e-6,
) -> dict[str, Any]:
    """Deterministic bounded budget allocation maximizing concave response sum.

    Enforces:
    - L_i <= x_i <= U_i for exactly the authorized channels
    - sum(x_i) <= B (and sum(x_i) == B if fixed_total)
    - Rejection of infeasible bounds (L_i > U_i, sum(L_i) > B, sum(U_i) < B for fixed_total)
    - Continuous water-filling bisection over shadow price lambda
    - Exact currency quantization and finite-gain residual allocation
    - Stable channel-ID tie-breaking
    """
    if budget < 0.0 or not math.isfinite(budget):
        return {
            "status": "error",
            "domain_status": SAllocDomainStatus.INVALID_INPUT.value,
            "error": f"Budget must be a finite non-negative number: {budget}",
        }
    if not channels:
        return {
            "status": "error",
            "domain_status": SAllocDomainStatus.INVALID_INPUT.value,
            "error": "Authorized channel set cannot be empty",
        }

    q = 10 ** (-currency_precision)
    min_map = min_spend or {}
    max_map = max_spend or {}
    slopes = initial_slopes or {}
    sats = saturation_spends or {}

    for ch in channels:
        a = slopes.get(ch)
        if a is not None:
            if not math.isfinite(a) or a < 0.0:
                return {
                    "status": "error",
                    "domain_status": SAllocDomainStatus.UNSUPPORTED_MODEL.value,
                    "error": f"Initial marginal return for channel '{ch}' must be finite and >= 0, got {a}",
                }
        s = sats.get(ch)
        if s is not None:
            if not math.isfinite(s) or s <= 0.0:
                return {
                    "status": "error",
                    "domain_status": SAllocDomainStatus.UNSUPPORTED_MODEL.value,
                    "error": f"Saturation spend for channel '{ch}' must be finite and > 0, got {s}",
                }

    # Exact currency quantization on bounds
    bounds_l: dict[str, float] = {}
    bounds_u: dict[str, float] = {}

    for ch in channels:
        raw_l = max(0.0, min_map.get(ch, 0.0))
        raw_u = max(0.0, max_map.get(ch, budget))

        # Quantize minimum upward and maximum downward to minor units
        quantized_l = round(math.ceil(round(raw_l / q, 6)) * q, currency_precision)
        quantized_u = round(math.floor(round(raw_u / q, 6)) * q, currency_precision)

        if quantized_l > quantized_u + 1e-9:
            return {
                "status": "error",
                "domain_status": SAllocDomainStatus.INFEASIBLE.value,
                "error": (
                    f"Channel minimum ({quantized_l:.2f}) exceeds maximum ({quantized_u:.2f}) "
                    f"for channel '{ch}'"
                ),
            }
        bounds_l[ch] = quantized_l
        bounds_u[ch] = quantized_u

    total_min = round(sum(bounds_l.values()), currency_precision)
    total_max = round(sum(bounds_u.values()), currency_precision)

    if total_min > budget + 1e-9:
        return {
            "status": "error",
            "domain_status": SAllocDomainStatus.INFEASIBLE.value,
            "error": (
                f"Sum of channel minimums ({total_min:.2f}) exceeds budget ({budget:.2f})"
            ),
        }
    if fixed_total and total_max < budget - 1e-9:
        return {
            "status": "error",
            "domain_status": SAllocDomainStatus.INFEASIBLE.value,
            "error": (
                f"Sum of channel maximums ({total_max:.2f}) is less than fixed budget ({budget:.2f})"
            ),
        }

    # Zero budget fast-path
    if budget == 0.0:
        zero_allocs = {ch: 0.0 for ch in channels}
        zero_mroi = {
            ch: round(slopes.get(ch, 0.0), 4) for ch in channels
        }
        return {
            "status": "success",
            "domain_status": SAllocDomainStatus.OK.value,
            "allocations": zero_allocs,
            "allocated_total": 0.0,
            "budget_residual": 0.0,
            "bound_residuals": {
                ch: {"lower_slack": 0.0, "upper_slack": bounds_u[ch]} for ch in channels
            },
            "active_bounds": {ch: "MIN" for ch in channels},
            "marginal_roas": zero_mroi,
            "expected_blended_roas": 0.0,
            "objective_value": 0.0,
            "iterations": 0,
            "stop_reason": "zero_budget",
        }

    # Continuous water-filling bisection over shadow price lambda
    def x_lambda(ch: str, lam: float) -> float:
        a = slopes.get(ch, 0.0)
        s = sats.get(ch, 1.0)
        low = bounds_l[ch]
        high = bounds_u[ch]
        if a <= 0.0 or lam <= 0.0:
            return low
        ratio = a / lam
        if ratio <= 1.0:
            return low
        x_val = s * (math.sqrt(ratio) - 1.0)
        return max(low, min(high, x_val))

    # Determine bisection bracket for lambda
    max_slope = max([slopes.get(ch, 0.0) for ch in channels] + [1.0])
    lam_high = max(max_slope * 2.0, 1.0)
    lam_low = max(mroi_floor, 1e-8)

    lam_best = lam_high
    iterations = 0
    stop_reason = "converged"

    if sum(x_lambda(ch, lam_high) for ch in channels) >= budget - 1e-9:
        lam_best = lam_high
        stop_reason = "minimum_bounds_active"
    elif sum(x_lambda(ch, lam_low) for ch in channels) <= budget + 1e-9:
        lam_best = lam_low
        stop_reason = "maximum_bounds_active"
    else:
        lo = lam_low
        hi = lam_high
        for it in range(max_iterations):
            iterations = it + 1
            mid = (lo + hi) / 2.0
            sum_mid = sum(x_lambda(ch, mid) for ch in channels)
            if abs(sum_mid - budget) <= max(tolerance * budget, 1e-6) or (hi - lo) < 1e-12:
                lam_best = mid
                break
            if sum_mid > budget:
                lo = mid
            else:
                hi = mid
        lam_best = (lo + hi) / 2.0

    # Conservative currency quantization
    allocations: dict[str, float] = {}
    for ch in channels:
        continuous_x = x_lambda(ch, lam_best)
        quantized = round(math.floor(round(continuous_x / q, 6)) * q, currency_precision)
        quantized = max(bounds_l[ch], min(bounds_u[ch], quantized))
        allocations[ch] = quantized

    # Allocate residual minor-unit quanta by finite incremental gain
    allocated_sum = round(sum(allocations.values()), currency_precision)
    rem_budget = round(budget - allocated_sum, currency_precision)

    while rem_budget >= q - 1e-9:
        eligible_candidates: list[tuple[float, str]] = []
        for ch in channels:
            if allocations[ch] + q <= bounds_u[ch] + 1e-9:
                a_val = slopes.get(ch, 0.0)
                s_val = sats.get(ch, 1.0)
                gain = finite_incremental_gain(a_val, s_val, allocations[ch], q)
                # Check mROI floor for discretionary increments
                if mroi_floor <= 0.0 or (gain / q) >= mroi_floor - 1e-9:
                    eligible_candidates.append((gain, ch))

        if not eligible_candidates:
            break

        # Maximize gain with stable alphabetical channel tie-breaking
        eligible_candidates.sort(key=lambda item: (-item[0], item[1]))
        best_gain, best_ch = eligible_candidates[0]
        allocations[best_ch] = round(allocations[best_ch] + q, currency_precision)
        rem_budget = round(rem_budget - q, currency_precision)

    final_allocated = round(sum(allocations.values()), currency_precision)
    budget_residual = round(max(0.0, budget - final_allocated), currency_precision)

    # Compute diagnostics, active bounds, and marginal returns
    active_bounds: dict[str, str] = {}
    bound_residuals: dict[str, dict[str, float]] = {}
    marginal_roas: dict[str, float] = {}
    objective_value = 0.0

    for ch in channels:
        amt = allocations[ch]
        low = bounds_l[ch]
        high = bounds_u[ch]
        a_val = slopes.get(ch, 0.0)
        s_val = sats.get(ch, 1.0)

        resp, mroi_val, _ = model_media_mix(ch, amt, a_val, s_val)
        objective_value += resp
        marginal_roas[ch] = round(mroi_val, 4)

        if abs(amt - low) < 1e-6:
            active_bounds[ch] = "MIN"
        elif abs(amt - high) < 1e-6:
            active_bounds[ch] = "MAX"
        else:
            active_bounds[ch] = "INTERIOR"

        bound_residuals[ch] = {
            "lower_slack": round(amt - low, currency_precision),
            "upper_slack": round(high - amt, currency_precision),
        }

    expected_blended_roas = calculate_roas(allocations, slopes, sats)

    return {
        "status": "success",
        "domain_status": SAllocDomainStatus.OK.value,
        "allocations": allocations,
        "allocated_total": final_allocated,
        "budget_residual": budget_residual,
        "bound_residuals": bound_residuals,
        "active_bounds": active_bounds,
        "marginal_roas": marginal_roas,
        "expected_blended_roas": round(expected_blended_roas, 4),
        "objective_value": round(objective_value, 4),
        "iterations": iterations,
        "stop_reason": stop_reason,
    }


# =============================================================================
# 3. Multi-Scenario Simulation
# =============================================================================


def simulate_scenarios(
    budget: float,
    channels: list[str],
    min_spend: dict[str, float] | None = None,
    max_spend: dict[str, float] | None = None,
    initial_slopes: dict[str, float] | None = None,
    saturation_spends: dict[str, float] | None = None,
    mroi_floor: float = 0.0,
    currency_precision: int = 2,
    recommended_preference: str = "balanced",
) -> list[dict[str, Any]]:
    """Solve each scenario independently under authoritative budget and channel constraints.

    Never normalizes or relaxes bounds across scenarios.
    """
    slopes = dict(initial_slopes or {})
    sats = dict(saturation_spends or {})

    # 1. Balanced: unweighted optimization
    bal_res = optimize_budget(
        budget=budget,
        channels=channels,
        min_spend=min_spend,
        max_spend=max_spend,
        initial_slopes=slopes,
        saturation_spends=sats,
        mroi_floor=mroi_floor,
        currency_precision=currency_precision,
    )
    bal_allocs = bal_res.get("allocations", {c: 0.0 for c in channels})

    # 2. Aggressive: upper-funnel scale tilt subject to the same authoritative constraints
    agg_slopes = {
        ch: slopes[ch] * (1.25 if ch in {"meta", "tiktok", "youtube"} else 0.85)
        for ch in channels
    }
    agg_res = optimize_budget(
        budget=budget,
        channels=channels,
        min_spend=min_spend,
        max_spend=max_spend,
        initial_slopes=agg_slopes,
        saturation_spends=sats,
        mroi_floor=mroi_floor,
        currency_precision=currency_precision,
    )
    agg_allocs = agg_res.get("allocations", {c: 0.0 for c in channels})

    # 3. Conservative: conversion/efficiency tilt subject to the same authoritative constraints
    cons_slopes = {
        ch: slopes[ch] * (1.30 if ch in {"google", "email", "linkedin"} else 0.75)
        for ch in channels
    }
    cons_res = optimize_budget(
        budget=budget,
        channels=channels,
        min_spend=min_spend,
        max_spend=max_spend,
        initial_slopes=cons_slopes,
        saturation_spends=sats,
        mroi_floor=mroi_floor,
        currency_precision=currency_precision,
    )
    cons_allocs = cons_res.get("allocations", {c: 0.0 for c in channels})

    def calc_roas_for(allocs: dict[str, float]) -> float:
        return round(calculate_roas(allocs, slopes, sats), 2)

    scenarios = [
        {
            "scenario_id": "scenario_balanced",
            "scenario_name": "Balanced Omnichannel Growth",
            "description": "Marginal-return-aware constrained allocation balancing discovery with intent capture.",
            "is_recommended": recommended_preference == "balanced",
            "allocations_by_channel": bal_allocs,
            "allocations_by_stage": {
                "TOFU": round(budget * 0.40, 2),
                "MOFU": round(budget * 0.30, 2),
                "BOFU": round(budget * 0.20, 2),
                "RETENTION": round(max(0.0, budget * 0.10), 2),
            },
            "expected_blended_roas": calc_roas_for(bal_allocs),
            "allocated_total": bal_res.get("allocated_total", budget),
            "budget_residual": bal_res.get("budget_residual", 0.0),
            "risk_level": "medium",
            "key_assumptions": [
                "Planning response curves are proxies unless calibrated by experiments or a fitted MMM."
            ],
        },
        {
            "scenario_id": "scenario_aggressive",
            "scenario_name": "Aggressive Audience Scale",
            "description": "Tilts spend toward discovery/upper-funnel channels for rapid audience penetration.",
            "is_recommended": recommended_preference == "aggressive",
            "allocations_by_channel": agg_allocs,
            "allocations_by_stage": {
                "TOFU": round(budget * 0.60, 2),
                "MOFU": round(budget * 0.20, 2),
                "BOFU": round(budget * 0.15, 2),
                "RETENTION": round(max(0.0, budget * 0.05), 2),
            },
            "expected_blended_roas": calc_roas_for(agg_allocs),
            "allocated_total": agg_res.get("allocated_total", budget),
            "budget_residual": agg_res.get("budget_residual", 0.0),
            "risk_level": "high",
            "key_assumptions": [
                "Higher reach may encounter faster saturation and creative fatigue."
            ],
        },
        {
            "scenario_id": "scenario_conservative",
            "scenario_name": "Conservative ROAS-First",
            "description": "Tilts spend toward high-intent conversion and customer retention.",
            "is_recommended": recommended_preference == "conservative",
            "allocations_by_channel": cons_allocs,
            "allocations_by_stage": {
                "TOFU": round(budget * 0.30, 2),
                "MOFU": round(budget * 0.25, 2),
                "BOFU": round(budget * 0.30, 2),
                "RETENTION": round(max(0.0, budget * 0.15), 2),
            },
            "expected_blended_roas": calc_roas_for(cons_allocs),
            "allocated_total": cons_res.get("allocated_total", budget),
            "budget_residual": cons_res.get("budget_residual", 0.0),
            "risk_level": "low",
            "key_assumptions": [
                "Lower reach is accepted in exchange for near-term capital efficiency."
            ],
        },
    ]
    return scenarios


# =============================================================================
# 4. Funnel Stage Simulation
# =============================================================================


def simulate_funnel(
    allocated_total: float,
    channels: list[str],
    addressed_objections: bool = False,
    stage_rates: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Decompose allocated spend across marketing funnel stages."""
    tofu_pct, mofu_pct, bofu_pct, ret_pct = (
        (0.40, 0.30, 0.20, 0.10) if addressed_objections else (0.45, 0.25, 0.20, 0.10)
    )
    stage_pcts = [
        ("TOFU", tofu_pct),
        ("MOFU", mofu_pct),
        ("BOFU", bofu_pct),
        ("RETENTION", ret_pct),
    ]

    stage_amounts = {name: round(allocated_total * pct, 2) for name, pct in stage_pcts}
    stage_amounts["RETENTION"] = round(
        max(
            0.0,
            allocated_total
            - stage_amounts["TOFU"]
            - stage_amounts["MOFU"]
            - stage_amounts["BOFU"],
        ),
        2,
    )

    stage_full_names = {
        "TOFU": "Top of Funnel (Awareness & Discovery)",
        "MOFU": "Middle of Funnel (Consideration & Education)",
        "BOFU": "Bottom of Funnel (Conversion & Intent Capture)",
        "RETENTION": "Retention & Lifecycle Re-engagement",
    }
    mapping = {
        "TOFU": ["meta", "tiktok", "youtube"],
        "MOFU": ["meta", "youtube", "linkedin"],
        "BOFU": ["google", "meta"],
        "RETENTION": ["email", "meta"],
    }
    rates = stage_rates or {}

    funnel: list[dict[str, Any]] = []
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
            "target_metrics": rates.get(name, {}),
        })
    return funnel


# =============================================================================
# 5. Core Execution Dispatcher (execute_s_alloc & run_s_alloc)
# =============================================================================


def _float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        f = float(value)
        return f if math.isfinite(f) else default
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
    """Execute deterministic Media & Budget Allocation specialist task."""
    if not payload:
        return {
            "status": "error",
            "domain_status": SAllocDomainStatus.INVALID_INPUT.value,
            "error": "Empty input payload",
            "allocations": json.dumps({}),
            "model_diagnostics": json.dumps({
                "health_status": "FAIL",
                "domain_status": SAllocDomainStatus.INVALID_INPUT.value,
                "health_reasons": ["Empty input payload"],
            }),
        }

    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    brand_id = str(payload.get("brand_id", "default"))
    time_horizon = str(payload.get("time_horizon", "90_days"))
    objective = str(payload.get("objective", "balanced omnichannel planning"))

    # 1. Budget normalization
    raw_budget = payload.get("budget")
    if raw_budget is None:
        raw_budget = payload.get("budget_cap", payload.get("budget_ceiling", 10000.0))
    requested_budget = max(0.0, _float(raw_budget, 10000.0))

    raw_ceiling = payload.get("budget_ceiling")
    ceiling = max(0.0, _float(raw_ceiling, requested_budget))
    budget_total = min(requested_budget, ceiling)

    # 2. Channels normalization
    raw_channels = payload.get("channels")
    if raw_channels is None or (isinstance(raw_channels, str) and not raw_channels.strip()):
        channels = ["meta", "google", "tiktok"]
    elif isinstance(raw_channels, list):
        channels = [str(x).strip().lower() for x in raw_channels if str(x).strip()]
    else:
        channels = [x.strip().lower() for x in str(raw_channels).split(",") if x.strip()]

    if not channels:
        channels = ["meta", "google", "tiktok"]
    channels = list(dict.fromkeys(channels))

    defaults = {
        "meta": 3.2,
        "google": 3.8,
        "tiktok": 2.6,
        "linkedin": 2.1,
        "youtube": 2.9,
        "email": 4.5,
    }

    media_history = _json(
        payload.get("media_history") or payload.get("performance_telemetry"), {}
    )
    if not isinstance(media_history, dict):
        media_history = {}

    constraints = _json(payload.get("channel_constraints"), {})
    if not isinstance(constraints, dict):
        raw_c = _json(payload.get("constraints"), {})
        constraints = raw_c if isinstance(raw_c, dict) else {}

    reasoning = _json(payload.get("s_alloc_reasoning"), {})

    # Evidence: extract claims, objections, competitor signals
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
    if isinstance(comp, dict) and comp:
        name = comp.get("competitor", "Competitor")
        threat = str(comp.get("threat_level", "medium")).lower()
        sig = f"{name} threat: {threat}"
        if comp.get("benchmark_price") is not None:
            sig += f", benchmark price: ${comp.get('benchmark_price')}"
        factored_competitor_signals.append(sig)

    # Channel model parameters
    priors: dict[str, float] = {}
    saturation: dict[str, float] = {}
    min_spend_map: dict[str, float] = {}
    max_spend_map: dict[str, float] = {}

    for ch in channels:
        hist = media_history.get(ch, {}) if isinstance(media_history.get(ch, {}), dict) else {}
        prior_val = payload.get(f"prior_roas_{ch}")
        if prior_val is None:
            prior_val = hist.get("roi") or hist.get("prior_roas") if isinstance(hist, dict) else None
        priors[ch] = max(0.01, _float(prior_val, defaults.get(ch, 2.5)))

        sat_val = payload.get(f"saturation_spend_{ch}")
        if sat_val is None:
            sat_val = hist.get("saturation_spend") if isinstance(hist, dict) else None
        sat_default = max(budget_total / max(len(channels), 1), 1.0)
        saturation[ch] = max(1.0, _float(sat_val, sat_default))

        # Constraints
        c = constraints.get(ch, {}) if isinstance(constraints.get(ch, {}), dict) else {}
        mn = max(0.0, _float(c.get("min_spend"), 0.0))
        mx = max(0.0, _float(c.get("max_spend"), budget_total))
        if c.get("min_share") is not None:
            mn = max(mn, budget_total * max(0.0, min(1.0, _float(c.get("min_share"), 0.0))))
        if c.get("max_share") is not None:
            mx = min(mx, budget_total * max(0.0, min(1.0, _float(c.get("max_share"), 1.0))))
        min_spend_map[ch] = mn
        max_spend_map[ch] = mx

    # Optimize budget
    opt_result = optimize_budget(
        budget=budget_total,
        channels=channels,
        min_spend=min_spend_map,
        max_spend=max_spend_map,
        initial_slopes=priors,
        saturation_spends=saturation,
        mroi_floor=_float(payload.get("mroi_floor"), 0.0),
    )

    if opt_result["status"] != "success":
        domain_status = opt_result.get("domain_status", SAllocDomainStatus.INFEASIBLE.value)
        return {
            "status": "error",
            "domain_status": domain_status,
            "error": opt_result.get("error", "Optimization failed"),
            "task_id": task_id,
            "budget_total": str(budget_total),
            "allocated_total": "0.0",
            "allocations": json.dumps({}),
            "strategy_plan": "null",
            "model_diagnostics": json.dumps({
                "health_status": "FAIL",
                "domain_status": domain_status,
                "warnings": [opt_result.get("error", "Optimization failed")],
            }),
        }

    allocations = opt_result["allocations"]
    allocated_total = opt_result["allocated_total"]
    budget_residual = opt_result["budget_residual"]
    marginal_roas = opt_result["marginal_roas"]
    expected_blended_roas = opt_result["expected_blended_roas"]

    # Response curves
    curves: dict[str, list[dict[str, float]]] = {}
    for ch in channels:
        top = max(max_spend_map[ch], allocations[ch], saturation[ch])
        points: list[dict[str, float]] = []
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            spend_pt = round(top * frac, 2)
            resp, mroi_val, _ = model_media_mix(ch, spend_pt, priors[ch], saturation[ch])
            points.append({
                "spend": spend_pt,
                "expected_incremental_kpi": round(resp, 4),
                "mroi": round(mroi_val, 4),
            })
        curves[ch] = points

    # Funnel and Scenarios
    pref = (
        str(reasoning.get("scenario_emphasis", "")).lower()
        if isinstance(reasoning, dict)
        else ""
    )
    if pref not in {"balanced", "aggressive", "conservative"}:
        low = objective.lower()
        if any(x in low for x in ("efficiency", "profit", "roas", "margin")):
            pref = "conservative"
        elif any(x in low for x in ("awareness", "reach", "scale", "growth")):
            pref = "aggressive"
        else:
            pref = "balanced"

    scenarios = simulate_scenarios(
        budget=budget_total,
        channels=channels,
        min_spend=min_spend_map,
        max_spend=max_spend_map,
        initial_slopes=priors,
        saturation_spends=saturation,
        mroi_floor=_float(payload.get("mroi_floor"), 0.0),
        recommended_preference=pref,
    )

    funnel = simulate_funnel(
        allocated_total=allocated_total,
        channels=channels,
        addressed_objections=bool(addressed_objections),
    )

    # Explicit Model Health Diagnostics
    health_reasons = [
        "Current implementation is a deterministic response-curve planning proxy, not a fitted causal MMM."
    ]
    if not media_history:
        health_reasons.append("No media-history/performance series supplied.")

    health_status = "REVIEW"
    if budget_total <= 0.0 or not channels:
        health_status = "FAIL"
        health_reasons.append("Budget total is zero or channel set is empty.")

    model_diagnostics = {
        "measurement_mode": "deterministic_response_curve_proxy",
        "causal_mmm": False,
        "health_status": health_status,
        "health_reasons": health_reasons,
        "incrementality_calibrated": False,
        "marginal_roas": marginal_roas,
        "domain_status": SAllocDomainStatus.OK.value,
        "warnings": [],
    }

    # Channel spend proposal objects for Strategy plan
    channel_objs: list[dict[str, Any]] = []
    roles_map = {
        "meta": "Top-of-funnel acquisition, discovery, and dynamic retargeting",
        "google": "High-intent search capture and competitor brand defense",
        "tiktok": "Short-form video discovery and social proof",
        "linkedin": "B2B consideration, authority, and partner outreach",
        "youtube": "Mid-funnel video education and brand lift",
        "email": "Retention, lifecycle re-engagement, and repeat subscriptions",
    }
    for ch in channels:
        pct = (allocations[ch] / budget_total * 100.0) if budget_total > 0 else 0.0
        channel_objs.append({
            "channel": ch,
            "allocated_amount": allocations[ch],
            "percentage_of_total": round(pct, 1),
            "role": roles_map.get(ch, f"Omnichannel activation on {ch}"),
            "primary_kpi": "mROI / incremental KPI",
            "prior_roas": priors[ch],
            "target_roas_range": [round(priors[ch] * 0.8, 2), round(priors[ch] * 1.2, 2)],
            "constraints": [
                f"min=${min_spend_map[ch]:.2f}",
                f"max=${max_spend_map[ch]:.2f}",
                f"saturation=${saturation[ch]:.2f}",
            ],
        })

    # Strategy plan assembly
    plan = {
        "plan_id": f"strat-{task_id}",
        "tenant_id": tenant_id,
        "brand_id": brand_id,
        "time_horizon": time_horizon,
        "budget_ceiling": ceiling,
        "total_allocated": allocated_total,
        "unallocated_contingency": budget_residual,
        "channel_allocations": channel_objs,
        "funnel_stages": funnel,
        "scenarios": scenarios,
        "recommended_scenario": f"scenario_{pref}",
        "approved_claims_applied": applied_claims,
        "objections_addressed": addressed_objections,
        "competitor_signals_factored": factored_competitor_signals,
        "assumptions": [
            "Response curves use a saturating planning proxy and must not be represented as causal MMM estimates.",
            "All budget allocations strictly satisfy authoritative ceiling and channel bounds.",
        ],
        "constraints": [
            f"Total budget proposal strictly capped at authorized ceiling of ${ceiling:.2f}.",
            f"Channels restricted to: {', '.join(channels)}.",
            "No automated outbound campaign publishing or spend modification without explicit HITL sign-off.",
        ],
        "unsupported_estimates_or_caveats": list(health_reasons) + [
            "Projected ROI/mROI values are planning estimates, not guaranteed financial results."
        ],
        "provenance": {
            "modeled_by": "S_ALLOC",
            "task_id": task_id,
            "tenant_id": tenant_id,
            "model_diagnostics": model_diagnostics,
        },
        "confidence": {
            "point_estimate": round(
                min(
                    0.85,
                    0.65
                    + (0.05 if applied_claims else 0.0)
                    + (0.05 if addressed_objections else 0.0)
                    + (0.05 if factored_competitor_signals else 0.0)
                    + (0.05 if media_history else 0.0),
                ),
                2,
            ),
            "lower_bound": round(
                max(
                    0.0,
                    min(
                        0.85,
                        0.65
                        + (0.05 if applied_claims else 0.0)
                        + (0.05 if addressed_objections else 0.0)
                        + (0.05 if factored_competitor_signals else 0.0)
                        + (0.05 if media_history else 0.0),
                    )
                    - 0.15,
                ),
                2,
            ),
            "upper_bound": round(
                min(
                    1.0,
                    min(
                        0.85,
                        0.65
                        + (0.05 if applied_claims else 0.0)
                        + (0.05 if addressed_objections else 0.0)
                        + (0.05 if factored_competitor_signals else 0.0)
                        + (0.05 if media_history else 0.0),
                    )
                    + 0.10,
                ),
                2,
            ),
        },
    }

    primary = max(allocations, key=lambda k: allocations[k]) if allocations else "none"

    result: dict[str, str] = {
        "status": "success",
        "domain_status": SAllocDomainStatus.OK.value,
        "task_id": task_id,
        "budget_total": str(budget_total),
        "allocated_total": str(allocated_total),
        "budget_residual": str(budget_residual),
        "allocations": json.dumps(allocations),
        "expected_blended_roas": f"{expected_blended_roas:.2f}",
        "primary_channel": primary,
        "marginal_roas": json.dumps(marginal_roas),
        "response_curves": json.dumps(curves),
        "model_diagnostics": json.dumps(model_diagnostics),
        "funnel_model": json.dumps(funnel),
        "scenarios": json.dumps(scenarios),
        "strategy_plan": json.dumps(plan),
    }
    if reasoning:
        result["s_alloc_reasoning"] = json.dumps(reasoning)

    return result


# Capability / Operation Aliases
allocation_solver = optimize_budget
diminishing_returns_model = model_media_mix
optimization_modeler = optimize_budget
run_s_alloc = execute_s_alloc
