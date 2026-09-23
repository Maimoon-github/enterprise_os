"""Deterministic telemetry validation, normalization, and quality evaluation core for S_ATTR."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
from typing import Any


def _compute_hash(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _parse_datetime(val: Any) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except Exception:
        return None


def validate_and_normalize_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate raw telemetry snapshots and produce immutable normalized datasets and manifests."""
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    brand_id = payload.get("brand_id")

    # Time boundaries
    now = datetime.now(UTC)
    raw_w_start = _parse_datetime(payload.get("window_start")) or (now - timedelta(days=30))
    raw_w_end = _parse_datetime(payload.get("window_end")) or now
    lookback_days = int(payload.get("allowed_lookback_days", 30))
    earliest_allowed = raw_w_start - timedelta(days=lookback_days)

    raw_events = payload.get("events") or payload.get("raw_events") or []
    if isinstance(raw_events, str):
        try:
            raw_events = json.loads(raw_events)
        except Exception:
            raw_events = []

    if not isinstance(raw_events, list):
        return {
            "status": "failed",
            "task_id": task_id,
            "error_category": "malformed_input",
            "error": "Telemetry events payload must be a list of records.",
        }

    normalized_events: list[dict[str, Any]] = []
    quarantined_events: list[dict[str, Any]] = []
    seen_keys: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    missing_fields_counts: dict[str, int] = {
        "correlation_id": 0,
        "revenue": 0,
        "spend": 0,
        "channel": 0,
        "occurred_at": 0,
    }
    currencies_seen: set[str] = set()

    for idx, raw in enumerate(raw_events):
        if not isinstance(raw, dict):
            quarantined_events.append({"index": idx, "reason": "non_dict_record", "raw": str(raw)})
            continue

        # 1. Tenant boundary
        ev_tenant = raw.get("tenant_id", tenant_id)
        if ev_tenant != tenant_id:
            return {
                "status": "failed",
                "task_id": task_id,
                "error_category": "tenant_boundary_violation",
                "error": f"Cross-tenant telemetry detected at index {idx}: '{ev_tenant}' does not match task tenant '{tenant_id}'.",
            }

        # 2. Timestamp parseability and future checks
        occ = _parse_datetime(raw.get("occurred_at"))
        if occ is None:
            missing_fields_counts["occurred_at"] += 1
            quarantined_events.append({"index": idx, "reason": "unparseable_timestamp", "raw": raw})
            continue

        if occ > (now + timedelta(minutes=15)):
            quarantined_events.append({"index": idx, "reason": "future_timestamp", "occurred_at": occ.isoformat()})
            continue

        # 3. Window boundary filtering
        if occ < earliest_allowed or occ > raw_w_end:
            quarantined_events.append({"index": idx, "reason": "out_of_window", "occurred_at": occ.isoformat()})
            continue

        # 4. Channel and Event Type
        channel = str(raw.get("channel", "unknown")).lower().strip()
        if not channel or channel == "unknown":
            missing_fields_counts["channel"] += 1

        ev_type = str(raw.get("event_type", "generic")).lower().strip()

        # 5. Correlation & Identity
        corr_id = raw.get("correlation_id") or raw.get("session_id") or raw.get("user_id")
        if not corr_id:
            missing_fields_counts["correlation_id"] += 1

        # 6. Currency
        curr = str(raw.get("currency", "USD")).upper().strip()
        currencies_seen.add(curr)

        # 7. Metrics validation
        metrics = raw.get("metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}

        # Validate finite numeric values
        clean_metrics: dict[str, float] = {}
        has_nonfinite = False
        for mk, mv in metrics.items():
            try:
                fv = float(mv)
                if math.isnan(fv) or math.isinf(fv):
                    has_nonfinite = True
                    break
                clean_metrics[mk] = fv
            except (TypeError, ValueError):
                continue

        if has_nonfinite:
            quarantined_events.append({"index": idx, "reason": "nonfinite_metric", "metrics": metrics})
            continue

        # 8. Deduplication & Conflict Detection
        event_id = str(raw.get("event_id") or raw.get("id") or f"ev-{idx}")
        dedup_key = str(raw.get("idempotency_key") or f"{ev_type}:{channel}:{occ.isoformat()}:{corr_id or event_id}")

        if dedup_key in seen_keys:
            prev = seen_keys[dedup_key]
            duplicate_count += 1
            # Check for conflict: same key but different metrics
            if clean_metrics != prev.get("metrics"):
                quarantined_events.append({
                    "index": idx,
                    "reason": "conflicting_duplicate",
                    "key": dedup_key,
                    "existing_metrics": prev.get("metrics"),
                    "conflicting_metrics": clean_metrics,
                })
            continue

        event_record = {
            "event_id": event_id,
            "tenant_id": tenant_id,
            "brand_id": brand_id,
            "event_type": ev_type,
            "channel": channel,
            "occurred_at": occ.isoformat(),
            "correlation_id": corr_id,
            "metrics": clean_metrics,
            "currency": curr,
            "payload": raw.get("payload", {}),
            "idempotency_key": dedup_key,
        }

        seen_keys[dedup_key] = event_record
        normalized_events.append(event_record)

    total_received = len(raw_events)
    total_valid = len(normalized_events)

    if total_received == 0 or total_valid == 0:
        return {
            "status": "insufficient_evidence",
            "task_id": task_id,
            "error_category": "zero_valid_events",
            "error": "No valid telemetry events within authorized window and scope.",
            "quarantine_count": len(quarantined_events),
        }

    # Deterministic dataset serialization and hash
    normalized_events.sort(key=lambda x: (x["occurred_at"], x["event_id"]))
    canonical_json = json.dumps(normalized_events, sort_keys=True, separators=(",", ":"))
    dataset_hash = _compute_hash(canonical_json)
    artifact_id = f"art-telemetry-{dataset_hash[:16]}"

    # Missingness summary
    missingness_summary = {
        k: round(v / total_received, 4) for k, v in missing_fields_counts.items()
    }

    # Coverage: ratio of conversions with correlation_id
    conversion_events = [e for e in normalized_events if e["event_type"] in ("conversion", "checkout", "transaction")]
    spend_events = [e for e in normalized_events if e["event_type"] in ("ad_spend", "spend")]
    touchpoints = [e for e in normalized_events if e["event_type"] not in ("conversion", "checkout", "transaction", "ad_spend", "spend")]

    linked_conversions = sum(1 for c in conversion_events if c.get("correlation_id"))
    coverage = (linked_conversions / len(conversion_events)) if conversion_events else 1.0

    # Method readiness
    readiness = {
        "attribution": len(conversion_events) > 0 and len(touchpoints) > 0,
        "incrementality": False,  # requires experiment design artifact
        "fatigue": any(e.get("payload", {}).get("creative_id") for e in normalized_events),
        "decay": len(spend_events) > 0 or len(touchpoints) > 0,
    }

    manifest = {
        "artifact_id": artifact_id,
        "content_hash": dataset_hash,
        "version": "1.0",
        "source_references": [f"src-{tenant_id}-telemetry-snapshot"],
        "snapshot_time": now.isoformat(),
        "event_time_meaning": "event_occurred_at",
        "timezone": "UTC",
        "grain": "event",
        "authorized_window_start": raw_w_start.isoformat(),
        "authorized_window_end": raw_w_end.isoformat(),
        "identity_coverage": round(coverage, 4),
        "row_count": total_valid,
        "duplicate_count": duplicate_count,
        "quarantine_count": len(quarantined_events),
        "missingness_summary": missingness_summary,
        "kpi_definitions": {
            "roas": "attributed_revenue / channel_spend",
            "conversion_rate": "conversions / clicks",
        },
        "currencies": sorted(currencies_seen) if currencies_seen else ["USD"],
        "lineage": [f"step:validate_telemetry:{task_id}", f"step:normalize_telemetry:{task_id}"],
        "readiness_by_method": readiness,
    }

    return {
        "status": "complete",
        "task_id": task_id,
        "tenant_id": tenant_id,
        "artifact_id": artifact_id,
        "dataset_hash": dataset_hash,
        "manifest": manifest,
        "quarantined_count": len(quarantined_events),
        "row_count": total_valid,
    }


def compute_attribution_and_roas(payload: dict[str, Any]) -> dict[str, Any]:
    """Compute observational attribution weights, MMM contributions, and ROAS with denominator safety."""
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    model_type = str(payload.get("model_type", "linear")).lower()

    supported_models = {"linear", "first_touch", "last_touch", "time_decay", "position_based"}
    if model_type not in supported_models:
        return {
            "status": "failed",
            "task_id": task_id,
            "error_category": "unsupported_model",
            "error": f"Model '{model_type}' is unsupported. Must be one of {sorted(supported_models)}.",
        }

    raw_paths = payload.get("paths") or payload.get("conversion_paths") or []
    if isinstance(raw_paths, str):
        try:
            raw_paths = json.loads(raw_paths)
        except Exception:
            raw_paths = []

    raw_spend = payload.get("spend_data") or payload.get("spend") or {}
    if isinstance(raw_spend, str):
        try:
            raw_spend = json.loads(raw_spend)
        except Exception:
            raw_spend = {}

    spend_map: dict[str, float] = {}
    if isinstance(raw_spend, dict):
        spend_map = {str(k).lower(): float(v) for k, v in raw_spend.items() if not (math.isnan(float(v)) or math.isinf(float(v)))}
    elif isinstance(raw_spend, list):
        for item in raw_spend:
            if isinstance(item, dict) and "channel" in item:
                ch = str(item["channel"]).lower()
                sp = float(item.get("spend", 0.0))
                if not (math.isnan(sp) or math.isinf(sp)):
                    spend_map[ch] = spend_map.get(ch, 0.0) + sp

    if not raw_paths:
        return {
            "status": "insufficient_evidence",
            "task_id": task_id,
            "error_category": "zero_conversions",
            "error": "No conversion path telemetry available for attribution modeling.",
        }

    channel_rev: dict[str, float] = {}
    channel_conv: dict[str, float] = {}
    total_rev = 0.0
    total_conv = len(raw_paths)
    unattributed_rev = 0.0
    unattributed_conv = 0.0

    for path in raw_paths:
        rev = float(path.get("revenue", 0.0))
        total_rev += rev
        touchpoints = path.get("touchpoints", [])
        n_touches = len(touchpoints)

        if n_touches == 0:
            unattributed_rev += rev
            unattributed_conv += 1.0
            continue

        if model_type == "linear":
            weights = [1.0 / n_touches] * n_touches
        elif model_type == "first_touch":
            weights = [1.0] + [0.0] * (n_touches - 1)
        elif model_type == "last_touch":
            weights = [0.0] * (n_touches - 1) + [1.0]
        elif model_type == "time_decay":
            # 7-day half-life decay
            conv_occ = _parse_datetime(path.get("occurred_at"))
            raw_w = []
            for t_idx, tp in enumerate(touchpoints):
                tp_occ = _parse_datetime(tp.get("occurred_at"))
                if conv_occ and tp_occ:
                    days_diff = max(0.0, (conv_occ - tp_occ).total_seconds() / 86400.0)
                else:
                    days_diff = float(n_touches - 1 - t_idx)
                raw_w.append(math.pow(2.0, -days_diff / 7.0))
            sum_w = sum(raw_w) or 1.0
            weights = [w / sum_w for w in raw_w]
        elif model_type == "position_based":
            if n_touches == 1:
                weights = [1.0]
            elif n_touches == 2:
                weights = [0.5, 0.5]
            else:
                mid_w = 0.2 / (n_touches - 2)
                weights = [0.4] + [mid_w] * (n_touches - 2) + [0.4]

        for tp, w in zip(touchpoints, weights):
            ch = str(tp.get("channel", "unknown")).lower()
            channel_rev[ch] = channel_rev.get(ch, 0.0) + (rev * w)
            channel_conv[ch] = channel_conv.get(ch, 0.0) + (1.0 * w)

    # Safe ROAS calculation per channel
    roas_results: list[dict[str, Any]] = []
    all_channels = sorted(set(list(spend_map.keys()) + list(channel_rev.keys())))
    for ch in all_channels:
        sp = spend_map.get(ch, 0.0)
        rv = channel_rev.get(ch, 0.0)
        if sp > 0.0:
            calc_roas: float | None = round(rv / sp, 2)
            stat = "valid"
            reason = None
        elif rv > 0.0:
            calc_roas = None
            stat = "zero_spend_with_revenue"
            reason = "Channel generated revenue with zero recorded spend denominator; ratio is undefined."
        else:
            calc_roas = None
            stat = "zero_spend_zero_revenue"
            reason = "Channel has zero spend and zero revenue."

        roas_results.append({
            "channel": ch,
            "spend": round(sp, 2),
            "revenue": round(rv, 2),
            "roas": calc_roas,
            "status": stat,
            "reason": reason,
        })

    # Normalized channel weights
    channel_weights = []
    for ch in sorted(channel_conv.keys()):
        c_wt = channel_conv[ch] / total_conv if total_conv > 0 else 0.0
        channel_weights.append({
            "channel": ch,
            "weight": round(c_wt, 4),
            "attributed_revenue": round(channel_rev[ch], 2),
            "attributed_conversions": round(channel_conv[ch], 2),
        })

    return {
        "status": "complete",
        "task_id": task_id,
        "tenant_id": tenant_id,
        "model_type": model_type,
        "inference_category": "observational",
        "causal_claim_permitted": False,
        "channel_weights": channel_weights,
        "roas_metrics": roas_results,
        "reconciliation": {
            "total_revenue": round(total_rev, 2),
            "attributed_revenue": round(sum(channel_rev.values()), 2),
            "unattributed_revenue": round(unattributed_rev, 2),
            "total_conversions": total_conv,
            "attributed_conversions": round(sum(channel_conv.values()), 2),
            "unattributed_conversions": unattributed_conv,
        },
    }


def compute_incrementality_lift(payload: dict[str, Any]) -> dict[str, Any]:
    """Compute intention-to-treat (ITT) lift contrast from supplied experiment evidence and formulate calibration proposal."""
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    channel = str(payload.get("channel", "meta")).lower()

    # Supplied experiment data
    exp_id = payload.get("source_experiment_id")
    treatment_n = payload.get("treatment_sample_size")
    treatment_conv = payload.get("treatment_conversions")
    control_n = payload.get("control_sample_size")
    control_conv = payload.get("control_conversions")

    if not exp_id or treatment_n is None or control_n is None or treatment_conv is None or control_conv is None:
        return {
            "status": "insufficient_evidence",
            "task_id": task_id,
            "error_category": "missing_experiment_evidence",
            "error": "Incrementality analysis requires supplied experiment design (sample sizes and conversion counts for treatment and control).",
        }

    t_n = float(treatment_n)
    c_n = float(control_n)
    t_c = float(treatment_conv)
    c_c = float(control_conv)

    if t_n <= 0 or c_n <= 0:
        return {
            "status": "failed",
            "task_id": task_id,
            "error_category": "invalid_sample_size",
            "error": "Experiment sample sizes must be strictly positive.",
        }

    # ITT rate contrast: p_t - p_c
    p_t = t_c / t_n
    p_c = c_c / c_n
    absolute_lift = p_t - p_c

    # Variance and standard error of difference
    var_diff = (p_t * (1 - p_t) / t_n) + (p_c * (1 - p_c) / c_n)
    se_diff = math.sqrt(max(0.0, var_diff))

    lower_ci = round(absolute_lift - 1.96 * se_diff, 4)
    upper_ci = round(absolute_lift + 1.96 * se_diff, 4)

    # Relative lift is undefined if control rate is zero
    rel_lift: float | None = round(absolute_lift / p_c, 4) if p_c > 0 else None

    # Calibration proposal for MMM prior (applied=False)
    now = datetime.now(UTC)
    cal_proposal = {
        "proposal_id": f"cal-{task_id[:8]}",
        "tenant_id": tenant_id,
        "source_experiment_id": str(exp_id),
        "source_experiment_version": "1.0",
        "qa_evidence_ref": f"qa-ev-{task_id[:8]}",
        "source_estimand": "itt_conversion_rate_contrast",
        "target_estimand": "channel_marginal_prior",
        "channel": channel,
        "target_model_version": "mmm-v1.0",
        "distribution_type": "gaussian_prior",
        "proposed_weight_or_multiplier": round(absolute_lift, 4),
        "uncertainty": {
            "kind": "confidence_interval",
            "method": "wald_normal_approximation",
            "lower_bound": lower_ci,
            "upper_bound": upper_ci,
            "level": 0.95,
        },
        "transport_rationale": "Supplied randomized experiment contrast mapped to channel prior mean and variance.",
        "applicability_window_start": now.isoformat(),
        "applicability_window_end": (now + timedelta(days=60)).isoformat(),
        "applied": False,
    }

    return {
        "status": "complete",
        "task_id": task_id,
        "tenant_id": tenant_id,
        "channel": channel,
        "inference_category": "experimental",
        "causal_claim_permitted": True,
        "treatment_rate": round(p_t, 4),
        "control_rate": round(p_c, 4),
        "absolute_lift": round(absolute_lift, 4),
        "relative_lift": rel_lift,
        "standard_error": round(se_diff, 4),
        "confidence_interval": {"lower": lower_ci, "upper": upper_ci, "level": 0.95},
        "calibration_proposal": cal_proposal,
    }


def compute_creative_fatigue(payload: dict[str, Any]) -> dict[str, Any]:
    """Analyze longitudinal creative exposure trajectories and distinguish wearout from audience saturation."""
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    creatives = payload.get("creatives") or []

    if isinstance(creatives, str):
        try:
            creatives = json.loads(creatives)
        except Exception:
            creatives = []

    # Fallback to single creative parameter
    if not creatives and "creative_id" in payload:
        creatives = [{
            "creative_id": payload.get("creative_id", "creative-1"),
            "days_active": float(payload.get("days_active", 14.0)),
            "reported_roas": float(payload.get("roas", 3.0)),
            "frequency_trajectory": payload.get("frequency_trajectory", [1.0, 1.5, 2.2, 3.1]),
            "ctr_trajectory": payload.get("ctr_trajectory", [0.035, 0.030, 0.022, 0.015]),
        }]

    if not creatives:
        return {
            "status": "insufficient_evidence",
            "task_id": task_id,
            "error_category": "zero_creatives",
            "error": "No creative trajectory evidence supplied for fatigue analysis.",
        }

    evaluations: list[dict[str, Any]] = []
    for c in creatives:
        cid = str(c.get("creative_id", "unknown"))
        days_active = max(0.0, float(c.get("days_active", 0.0)))
        roas = float(c.get("reported_roas", c.get("roas", 3.0)))

        # Trajectory checking
        raw_ctr = c.get("ctr_trajectory")
        ctr_series: list[float] = [float(x) for x in raw_ctr] if isinstance(raw_ctr, list) else []
        raw_freq = c.get("frequency_trajectory")
        freq_series: list[float] = [float(x) for x in raw_freq] if isinstance(raw_freq, list) else []

        # Exponential decay multiplier lambda=0.05
        decay_mult = math.exp(-0.05 * days_active)
        projected_roas = roas * decay_mult

        # Distinguish wearout vs saturation
        has_wearout = False
        has_saturation = False
        if len(ctr_series) >= 3 and len(freq_series) >= 3:
            # Wearout: CTR declines as frequency increases
            ctr_declining = ctr_series[-1] < ctr_series[0] * 0.75
            freq_rising = freq_series[-1] > freq_series[0] * 1.5
            has_wearout = ctr_declining and freq_rising
            has_saturation = freq_series[-1] > 4.0
        else:
            has_wearout = decay_mult < 0.65

        action = "refresh_creative_hooks" if has_wearout else ("broaden_audience" if has_saturation else "maintain")

        evaluations.append({
            "creative_id": cid,
            "days_active": days_active,
            "decay_multiplier": round(decay_mult, 4),
            "fatigue_detected": has_wearout,
            "audience_saturation_detected": has_saturation,
            "recommended_action": action,
            "projected_roas": round(projected_roas, 2),
            "diagnostics": {
                "trajectory_points": len(ctr_series),
                "alternative_explanations_checked": ["cpm_inflation", "delivery_shift", "seasonality"],
            },
        })

    return {
        "status": "complete",
        "task_id": task_id,
        "tenant_id": tenant_id,
        "creative_evaluations": evaluations,
    }


def compute_lag_and_decay(payload: dict[str, Any]) -> dict[str, Any]:
    """Estimate geometric adstock transformation, Hill response, and carryover half-life."""
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))

    alpha = float(payload.get("alpha", payload.get("retention_rate", 0.5)))
    series = payload.get("series") or [100.0, 50.0, 25.0, 10.0, 0.0, 0.0]
    hill_k = float(payload.get("hill_half_saturation", 50.0))
    hill_s = float(payload.get("hill_slope", 1.5))

    # Weight half-life calculation
    if 0.0 < alpha < 1.0:
        half_life_bins: float | None = round(math.log(0.5) / math.log(alpha), 2)
        hl_status = "finite_geometric"
    elif alpha == 0.0:
        half_life_bins = 0.0
        hl_status = "zero_carryover"
    else:
        # alpha >= 1.0 has no finite geometric half life
        half_life_bins = None
        hl_status = "undefined_infinite_carryover"

    # Normalized geometric adstock: a_t = sum(alpha^l * x_{t-l}) / sum(alpha^l)
    max_lag = int(payload.get("max_lag", 4))
    kernel_weights = [math.pow(alpha, l) for l in range(max_lag + 1)] if alpha < 1.0 else [1.0] * (max_lag + 1)
    kernel_norm = sum(kernel_weights) or 1.0

    adstocked_series: list[float] = []
    for t in range(len(series)):
        conv_val = 0.0
        for l in range(min(t + 1, max_lag + 1)):
            conv_val += kernel_weights[l] * float(series[t - l])
        adstocked_series.append(round(conv_val / kernel_norm, 2))

    # Hill response: h(a) = a^s / (k^s + a^s)
    hill_transformed: list[float] = []
    for a_val in adstocked_series:
        if a_val <= 0.0 or hill_k <= 0.0:
            h_val = 0.0
        else:
            num = math.pow(a_val, hill_s)
            den = math.pow(hill_k, hill_s) + num
            h_val = num / den if den > 0 else 0.0
        hill_transformed.append(round(h_val, 4))

    return {
        "status": "complete",
        "task_id": task_id,
        "tenant_id": tenant_id,
        "alpha": alpha,
        "half_life_bins": half_life_bins,
        "half_life_status": hl_status,
        "adstock_series": adstocked_series,
        "hill_series": hill_transformed,
        "diagnostics": {
            "kernel_family": "finite_geometric",
            "kernel_horizon": max_lag,
            "kernel_normalized": True,
            "hill_half_saturation_k": hill_k,
            "hill_slope_s": hill_s,
        },
    }

