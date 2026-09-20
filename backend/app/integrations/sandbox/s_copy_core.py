"""Deterministic Creative Utilities and Validator Core for S_COPY.

Contains ONLY deterministic validation, screening, deduplication, and hashing tools:
- Schema / required-field validation
- Claim-reference validation
- Character / text limit validation
- Approved-channel checks
- Prohibited-term screening
- Aspect-ratio checks
- UI Safe-zone metadata checks
- Platform-format validation
- Exact / normalized deterministic deduplication
- Citation / reference validation
- Deterministic artifact hashing

Contains ZERO generative responsibility (no claim invention, no hook/headline/body
generation, no concept selection, no visual brief synthesis, no schedule creation,
no fallback evidence/strategy generation).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

STANDARD_ASPECT_RATIOS = frozenset({"1:1", "9:16", "16:9", "4:5", "1.91:1"})

SUPPORTED_CHANNELS = frozenset({
    "meta",
    "google",
    "tiktok",
    "linkedin",
    "instagram",
    "x",
    "youtube",
    "email",
})

# Canonical platform formatting constraints
PLATFORM_FORMAT_CONSTRAINTS: dict[str, dict[str, Any]] = {
    "google": {
        "formats": ["search_ad", "display_ad", "pmax"],
        "max_headline_chars": 30,
        "max_body_chars": 90,
        "allowed_aspect_ratios": ["1.91:1", "1:1"],
    },
    "meta": {
        "formats": ["feed_ad", "story_ad", "reel", "carousel"],
        "max_headline_chars": 40,
        "max_body_chars": 125,
        "allowed_aspect_ratios": ["1:1", "9:16", "4:5"],
    },
    "tiktok": {
        "formats": ["short_video_ad", "in_feed"],
        "max_headline_chars": 100,
        "max_body_chars": 2200,
        "allowed_aspect_ratios": ["9:16"],
    },
    "linkedin": {
        "formats": ["sponsored_content", "message_ad", "carousel"],
        "max_headline_chars": 70,
        "max_body_chars": 600,
        "allowed_aspect_ratios": ["1.91:1", "1:1", "4:5"],
    },
    "x": {
        "formats": ["post", "promoted_post"],
        "max_headline_chars": 100,
        "max_body_chars": 280,
        "allowed_aspect_ratios": ["16:9", "1:1"],
    },
    "email": {
        "formats": ["newsletter_campaign", "drip_campaign"],
        "max_headline_chars": 100,
        "max_body_chars": 5000,
        "allowed_aspect_ratios": ["600x300", "1:1"],
    },
}


def hash_artifact(data: Any) -> str:
    """Compute deterministic SHA-256 hash of an artifact string, dict, or list."""
    if isinstance(data, (dict, list)):
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    else:
        serialized = str(data)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def normalize_text_for_dedup(text: str) -> str:
    """Normalize text by lowercasing, stripping punctuation, and collapsing whitespace."""
    clean = re.sub(r"[^\w\s]", "", text.lower())
    return re.sub(r"\s+", " ", clean).strip()


def prohibited_term_check(
    text_or_items: str | list[Any] | dict[str, Any],
    prohibited_terms: list[str],
) -> dict[str, Any]:
    """Screen provided text or items against prohibited terms (case-insensitive)."""
    norm_terms = [t.strip().lower() for t in prohibited_terms if t.strip()]
    if not norm_terms:
        return {
            "is_clean": True,
            "detected_terms": [],
            "flagged_items": [],
            "clean_items": text_or_items if isinstance(text_or_items, list) else [text_or_items],
        }

    detected_terms: set[str] = set()
    flagged_items: list[Any] = []
    clean_items: list[Any] = []

    if isinstance(text_or_items, str):
        text_lower = text_or_items.lower()
        for term in norm_terms:
            if term in text_lower:
                detected_terms.add(term)
        return {
            "is_clean": len(detected_terms) == 0,
            "detected_terms": sorted(detected_terms),
            "flagged_items": [text_or_items] if detected_terms else [],
            "clean_items": [] if detected_terms else [text_or_items],
        }

    items = text_or_items if isinstance(text_or_items, list) else [text_or_items]
    for item in items:
        item_text = ""
        if isinstance(item, dict):
            item_text = " ".join(
                str(v)
                for k, v in item.items()
                if k in ("hook", "headline", "body", "body_copy", "caption", "text", "angle")
            )
        else:
            item_text = str(item)

        item_lower = item_text.lower()
        item_detected = [term for term in norm_terms if term in item_lower]
        if item_detected:
            detected_terms.update(item_detected)
            flagged_items.append({"item": item, "detected_terms": item_detected})
        else:
            clean_items.append(item)

    return {
        "is_clean": len(detected_terms) == 0,
        "detected_terms": sorted(detected_terms),
        "flagged_items": flagged_items,
        "clean_items": clean_items,
    }


def deduplicate_variants(
    variants: list[dict[str, Any]] | list[str],
    key: str | None = None,
) -> dict[str, Any]:
    """Deterministically deduplicate variants while preserving original ordering."""
    seen: set[str] = set()
    deduped: list[Any] = []
    duplicates_found: list[Any] = []

    for item in variants:
        if isinstance(item, dict):
            raw = (
                item.get(key)
                if key
                else item.get("hook")
                or item.get("headline")
                or item.get("body_copy")
                or json.dumps(item, sort_keys=True)
            )
            norm = normalize_text_for_dedup(str(raw))
        else:
            norm = normalize_text_for_dedup(item)

        if norm in seen:
            duplicates_found.append(item)
        else:
            seen.add(norm)
            deduped.append(item)

    return {
        "deduplicated": deduped,
        "original_count": len(variants),
        "unique_count": len(deduped),
        "duplicates_removed": len(duplicates_found),
        "duplicates": duplicates_found,
    }


def validate_claim_refs(
    cited_claim_ids: list[str],
    approved_claims: list[dict[str, Any]] | list[str],
) -> dict[str, Any]:
    """Verify that cited claims strictly exist in the approved claims set."""
    approved_ids: set[str] = set()
    approved_texts: set[str] = set()

    for c in approved_claims:
        if isinstance(c, dict):
            status = c.get("validation_status", c.get("status", "SUPPORTED"))
            confidence = float(str(c.get("confidence", 1.0)))
            if status in ("SUPPORTED", "VALIDATED") or confidence >= 0.7:
                c_id = str(c.get("id") or c.get("claim_id") or "")
                c_text = str(c.get("text") or c.get("claim_text") or "")
                if c_id:
                    approved_ids.add(c_id)
                if c_text:
                    approved_texts.add(c_text)
        elif isinstance(c, str) and c.strip():
            approved_ids.add(c.strip())

    unsupported: list[str] = []
    valid_citations: list[str] = []

    for cid in cited_claim_ids:
        c_str = cid.strip()
        if c_str in approved_ids or c_str in approved_texts:
            valid_citations.append(c_str)
        else:
            unsupported.append(c_str)

    return {
        "all_grounded": len(unsupported) == 0,
        "approved_claim_ids": sorted(approved_ids),
        "valid_citations": valid_citations,
        "unsupported_claims": unsupported,
    }


def validate_aspect_ratio(
    aspect_ratio: str,
    allowed_ratios: list[str] | None = None,
) -> dict[str, Any]:
    """Validate aspect ratio against standard or platform-allowed aspect ratios."""
    allowed = set(allowed_ratios) if allowed_ratios else STANDARD_ASPECT_RATIOS
    is_valid = aspect_ratio in allowed
    return {
        "is_valid": is_valid,
        "aspect_ratio": aspect_ratio,
        "allowed_ratios": sorted(allowed),
    }


def validate_safe_zone_metadata(safe_zones: dict[str, Any]) -> dict[str, Any]:
    """Validate that UI safe-zone specifications contain valid non-negative margins."""
    errors: list[str] = []
    if not isinstance(safe_zones, dict):
        return {
            "is_valid": False,
            "errors": ["Safe-zone metadata must be a dictionary."],
            "safe_zones": {},
        }

    for key, val in safe_zones.items():
        try:
            num = float(val)
            if num < 0:
                errors.append(f"Safe zone dimension '{key}' cannot be negative: {val}")
        except (ValueError, TypeError):
            errors.append(f"Safe zone dimension '{key}' must be numeric: {val}")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "safe_zones": safe_zones,
    }


def validate_platform_format(
    channel: str,
    format_type: str | None = None,
    character_count: int | None = None,
    aspect_ratio: str | None = None,
) -> dict[str, Any]:
    """Deterministically check channel formatting, post type, char limits, and ratios."""
    ch_lower = channel.lower().strip()
    errors: list[str] = []

    if ch_lower not in SUPPORTED_CHANNELS:
        errors.append(f"Channel '{ch_lower}' is not an approved channel.")

    specs = PLATFORM_FORMAT_CONSTRAINTS.get(ch_lower)
    if specs:
        if format_type and format_type not in specs["formats"]:
            errors.append(
                f"Format '{format_type}' is invalid for channel '{ch_lower}'. "
                f"Allowed: {specs['formats']}"
            )
        if character_count is not None and character_count > specs["max_body_chars"]:
            errors.append(
                f"Character count {character_count} exceeds channel '{ch_lower}' "
                f"maximum limit of {specs['max_body_chars']}."
            )
        if aspect_ratio and aspect_ratio not in specs["allowed_aspect_ratios"]:
            errors.append(
                f"Aspect ratio '{aspect_ratio}' is not supported for channel '{ch_lower}'. "
                f"Allowed: {specs['allowed_aspect_ratios']}"
            )

    return {
        "is_valid": len(errors) == 0,
        "channel": ch_lower,
        "format": format_type,
        "errors": errors,
    }


def validate_schema(data: dict[str, Any], required_fields: list[str]) -> dict[str, Any]:
    """Verify presence of required fields in artifact or metadata dictionaries."""
    missing = [f for f in required_fields if f not in data or data[f] is None]
    return {
        "is_valid": len(missing) == 0,
        "missing_fields": missing,
        "present_fields": [f for f in required_fields if f in data and data[f] is not None],
    }


def execute_s_copy(payload: dict[str, Any]) -> dict[str, str]:
    """S_COPY: Deterministic Creative Utilities [Micro-Tool: Validator, Screener, Deduplicator].

    Strictly deterministic. Performs:
    1. Prohibited term screening
    2. Claim reference validation against approved evidence
    3. Platform format and character limit checking
    4. Aspect-ratio and UI safe-zone validation
    5. Deduplication of copy variants
    6. Artifact hashing

    Does NOT fabricate claims, hooks, headlines, visual briefs, social posts, or schedules.
    """
    task_id = str(payload.get("task_id", "unknown"))
    brand_voice = str(payload.get("brand_voice", "authoritative"))
    operation = str(payload.get("operation", "default"))

    # 1. Parse Prohibited Terms
    prohibited_raw = payload.get("prohibited_terms", "")
    prohibited_terms: list[str] = []
    if isinstance(prohibited_raw, list):
        prohibited_terms = [str(t).strip().lower() for t in prohibited_raw if str(t).strip()]
    elif isinstance(prohibited_raw, str):
        prohibited_terms = [t.strip().lower() for t in prohibited_raw.split(",") if t.strip()]

    # 2. Parse Approved Claims (T16)
    raw_claims = payload.get("t16_claims") or payload.get("approved_claims")
    claims_list: list[dict[str, Any]] = []
    if raw_claims:
        if isinstance(raw_claims, str):
            try:
                parsed = json.loads(raw_claims)
                claims_list = parsed if isinstance(parsed, list) else [parsed]
            except Exception:
                claims_list = [{"id": "claim-0", "text": raw_claims}]
        elif isinstance(raw_claims, list):
            claims_list = [c if isinstance(c, dict) else {"id": str(c), "text": str(c)} for c in raw_claims]

    approved_claim_ids: list[str] = []
    for c in claims_list:
        status = c.get("validation_status", c.get("status", "SUPPORTED"))
        conf = float(str(c.get("confidence", 1.0)))
        if status in ("SUPPORTED", "VALIDATED") or conf >= 0.7:
            cid = str(c.get("id") or c.get("claim_id") or "")
            if cid:
                approved_claim_ids.append(cid)

    # 3. Parse Unapproved / Unsupported Claims
    flagged_unsupported_claims: list[str] = []
    raw_unapproved = payload.get("unapproved_claims") or payload.get("raw_unapproved_claims")
    if raw_unapproved:
        if isinstance(raw_unapproved, str):
            try:
                unapproved_list = json.loads(raw_unapproved)
                if not isinstance(unapproved_list, list):
                    unapproved_list = [raw_unapproved]
            except Exception:
                unapproved_list = [c.strip() for c in raw_unapproved.split(",") if c.strip()]
        elif isinstance(raw_unapproved, list):
            unapproved_list = list(raw_unapproved)
        else:
            unapproved_list = []
        for u in unapproved_list:
            u_text = str(u.get("text", u) if isinstance(u, dict) else u)
            flagged_unsupported_claims.append(u_text)

    # 4. Parse Candidate Variants if passed
    raw_variants = payload.get("variants") or payload.get("candidate_variants") or payload.get("ad_copy_variants")
    input_variants: list[dict[str, Any]] = []
    if raw_variants:
        if isinstance(raw_variants, str):
            try:
                parsed_v = json.loads(raw_variants)
                input_variants = parsed_v if isinstance(parsed_v, list) else [parsed_v]
            except Exception:
                input_variants = []
        elif isinstance(raw_variants, list):
            input_variants = [v if isinstance(v, dict) else {"hook": str(v)} for v in raw_variants]

    # Specific Sub-Operation Dispatch
    if operation == "prohibited_term_check":
        screening = prohibited_term_check(
            input_variants or payload.get("text", ""),
            prohibited_terms,
        )
        return {
            "status": "success" if screening["is_clean"] else "compliance_warning",
            "task_id": task_id,
            "tool": "S_COPY",
            "is_clean": str(screening["is_clean"]),
            "detected_terms": json.dumps(screening["detected_terms"]),
            "flagged_count": str(len(screening["flagged_items"])),
            "clean_variants": json.dumps(screening["clean_items"]),
        }

    if operation == "deduplicate_variants":
        dedup_res = deduplicate_variants(input_variants)
        return {
            "status": "success",
            "task_id": task_id,
            "tool": "S_COPY",
            "original_count": str(dedup_res["original_count"]),
            "unique_count": str(dedup_res["unique_count"]),
            "duplicates_removed": str(dedup_res["duplicates_removed"]),
            "variants": json.dumps(dedup_res["deduplicated"]),
        }

    if operation == "validate_claim_refs":
        cited = [str(c) for c in (payload.get("source_claim_ids") or [])]
        claim_res = validate_claim_refs(cited, claims_list)
        return {
            "status": "success" if claim_res["all_grounded"] else "compliance_warning",
            "task_id": task_id,
            "tool": "S_COPY",
            "all_grounded": str(claim_res["all_grounded"]),
            "valid_citations": json.dumps(claim_res["valid_citations"]),
            "unsupported_claims": json.dumps(claim_res["unsupported_claims"]),
            "approved_claims_count": str(len(claim_res["approved_claim_ids"])),
        }

    if operation == "validate_aspect_ratio":
        ar = str(payload.get("aspect_ratio", "1:1"))
        allowed = payload.get("allowed_ratios")
        ar_res = validate_aspect_ratio(ar, allowed)
        return {
            "status": "success" if ar_res["is_valid"] else "validation_error",
            "task_id": task_id,
            "tool": "S_COPY",
            "is_valid": str(ar_res["is_valid"]),
            "aspect_ratio": ar,
            "allowed_ratios": json.dumps(ar_res["allowed_ratios"]),
        }

    if operation == "validate_safe_zone_metadata":
        sz = payload.get("safe_zones", {})
        sz_res = validate_safe_zone_metadata(sz)
        return {
            "status": "success" if sz_res["is_valid"] else "validation_error",
            "task_id": task_id,
            "tool": "S_COPY",
            "is_valid": str(sz_res["is_valid"]),
            "errors": json.dumps(sz_res["errors"]),
        }

    if operation == "validate_platform_format":
        ch = str(payload.get("channel", "meta"))
        fmt = payload.get("format")
        chars = int(payload.get("character_count", 0)) if payload.get("character_count") else None
        ar = payload.get("aspect_ratio")
        pf_res = validate_platform_format(ch, fmt, chars, ar)
        return {
            "status": "success" if pf_res["is_valid"] else "validation_error",
            "task_id": task_id,
            "tool": "S_COPY",
            "is_valid": str(pf_res["is_valid"]),
            "errors": json.dumps(pf_res["errors"]),
        }

    if operation == "hash_artifact":
        art_hash = hash_artifact(payload.get("artifact", payload))
        return {
            "status": "success",
            "task_id": task_id,
            "tool": "S_COPY",
            "artifact_hash": art_hash,
        }

    # Default / Composite Validation (validate_copy / format_validation / default)
    # 5. Deterministic screening & deduplication of candidate variants
    clean_variants: list[dict[str, Any]] = []
    compliance_warnings: list[str] = []

    if input_variants:
        screening = prohibited_term_check(input_variants, prohibited_terms)
        if not screening["is_clean"]:
            compliance_warnings.append(
                f"Prohibited terms detected: {screening['detected_terms']}"
            )
        dedup_res = deduplicate_variants(screening["clean_items"])
        clean_variants = dedup_res["deduplicated"]

    for u in flagged_unsupported_claims:
        compliance_warnings.append(f"Unsupported claim flagged: {u}")

    art_hash = hash_artifact({
        "task_id": task_id,
        "clean_variants": clean_variants,
        "approved_claims": approved_claim_ids,
        "flagged_claims": flagged_unsupported_claims,
    })

    # Return deterministic validation envelope
    return {
        "status": "success",
        "task_id": task_id,
        "brand_voice": brand_voice,
        "tool": "S_COPY",
        "deterministic": "true",
        "generative_execution": "denied",
        "message": (
            "S_COPY contains deterministic utilities only; creative generation "
            "is restricted to Creative LLM specialists."
        ),
        "variants": json.dumps(clean_variants),
        "variants_count": str(len(clean_variants)),
        "approved_claims_count": str(len(approved_claim_ids)),
        "flagged_claims": json.dumps(flagged_unsupported_claims),
        "compliance_warnings": json.dumps(compliance_warnings),
        "artifact_hash": art_hash,
        "is_compliant": str(len(compliance_warnings) == 0),
    }
