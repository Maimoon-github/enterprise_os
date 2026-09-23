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
