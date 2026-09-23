"""S_PARSE Core Deterministic NLP Parsing and Scrubbing Routines.

Shared logic for sentiment classification, objection extraction, PII scrubbing,
and prompt injection neutralization across remote and local execution contracts.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# PII / Sensitive Data Redaction Patterns
REDACTION_PATTERNS = [
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[REDACTED_EMAIL]"),
    (re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"), "[REDACTED_PHONE]"),
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[REDACTED_ACCOUNT]"),
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[REDACTED_IP]"),
    (re.compile(r"(?i)\b(?:customer|client|user|name is|i am)\s+(?!support|service|care|team|rep|agent|experience|feedback|review)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"), "[REDACTED_NAME]"),
    (re.compile(r"(?i)(api[_-]?key|secret|token|password|auth)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?"), "[REDACTED_SECRET]"),
]

# Prompt injection patterns inside customer voice data (neutralized fail-safe)
INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(?:all\s+)?(?:previous\s+)?instructions"),
    re.compile(r"(?i)system\s+(?:override|prompt)"),
    re.compile(r"(?i)you\s+are\s+now\s+(?:an?\s+)?unrestricted"),
    re.compile(r"(?i)grant\s+(?:admin|full)\s+access"),
    re.compile(r"(?i)execute\s+(?:code|command|tool)"),
    re.compile(r"(?i)output\s+(?:the\s+)?(?:secret|api_key|token)"),
]

# NLP Lexicons
POSITIVE_WORDS = frozenset({
    "love", "great", "excellent", "fast", "effective", "good", "best", "satisfied",
    "amazing", "smooth", "helpful", "impressed", "recommend", "reliable", "perfect",
    "fantastic", "quality", "friendly", "prompt", "easy", "delighted", "superb",
})

NEGATIVE_WORDS = frozenset({
    "slow", "expensive", "shipping", "broke", "delayed", "poor", "difficult", "bad",
    "terrible", "horrible", "awful", "defective", "useless", "damaged", "rude",
    "frustrated", "unacceptable", "broken", "crash", "refund", "leak", "stains",
    "missing", "confusing", "painful", "fail", "failed", "glitch", "flimsy",
    "unresponsive", "wait", "waited", "waiting", "issue", "problem", "complaint",
    "disappointed", "frustrating",
})

# Objection Category Triggers
OBJECTION_RULES: list[tuple[str, frozenset[str]]] = [
    ("fulfillment_delay", frozenset({"shipping", "delayed", "late", "delivery", "transit", "tracking", "package took", "never arrived"})),
    ("price_sensitivity", frozenset({"expensive", "price", "overpriced", "cost", "rip-off", "cheap", "subscription", "charge", "billing"})),
    ("customer_service_latency", frozenset({"support", "unresponsive", "hold", "agent", "ticket", "service", "reply", "representative", "chat"})),
    ("product_quality_defect", frozenset({"broke", "broken", "defective", "leak", "damaged", "faulty", "flimsy", "defect", "poor quality"})),
    ("usability_complexity", frozenset({"confusing", "difficult", "complicated", "instructions", "clunky", "complex", "hard to use"})),
    ("missing_feature", frozenset({"lacks", "missing", "wish it had", "no option for", "does not support", "feature"})),
]


def execute_s_parse_payload(payload: dict[str, Any]) -> dict[str, str]:
    """Execute S_PARSE NLP analysis over structured payload.

    Never fabricates fallback feedback text if evidence is missing.
    """
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    product_id = payload.get("product_id")

    # 1. Parse Input Items (support single feedback text or structured batch)
    raw_items = payload.get("items", payload.get("feedback_items"))
    items_list: list[dict[str, Any]] = []

    if raw_items:
        if isinstance(raw_items, str):
            try:
                parsed = json.loads(raw_items)
                items_list = parsed if isinstance(parsed, list) else [parsed]
            except Exception:
                items_list = [{"text": raw_items, "item_id": "item-0"}]
        elif isinstance(raw_items, list):
            items_list = raw_items
    elif "feedback_text" in payload or "query" in payload:
        single_text = payload.get("feedback_text") or payload.get("query")
        if single_text:
            items_list = [{
                "item_id": "item-0",
                "source_type": str(payload.get("source_type", "feedback")),
                "text": str(single_text),
                "product_id": product_id,
                "channel": payload.get("channel"),
                "tenant_id": tenant_id,
            }]

    if not items_list:
        return {
            "status": "incomplete",
            "task_id": task_id,
            "sentiment_polarity": "0.00",
            "primary_sentiment": "neutral",
            "objections": json.dumps(["none_detected"]),
            "feedback_summary": "Missing customer feedback evidence: cannot analyze empty input.",
            "customer_voice_analysis": json.dumps({
                "status": "incomplete",
                "reason": "missing_feedback_evidence",
                "total_items_analyzed": 0,
            }),
        }

    sentiment_vectors: list[dict[str, Any]] = []
    total_redactions = 0
    all_objections_flat: list[str] = []
    warnings: list[str] = []
    polarity_sum = 0.0

    sentiment_counts = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0, "MIXED": 0}

    # 2. Analyze Each Feedback Item
    for idx, raw_item in enumerate(items_list):
        item_id = str(raw_item.get("item_id", f"item-{idx + 1}"))
        raw_text = str(raw_item.get("text", ""))
        src_type = str(raw_item.get("source_type", "feedback"))
        item_channel = raw_item.get("channel")
        item_product = raw_item.get("product_id", product_id)

        # A. Prompt Injection Defense
        sanitized_text = raw_text
        for inj in INJECTION_PATTERNS:
            if inj.search(sanitized_text):
                warnings.append(f"Prompt injection pattern detected and neutralized in item '{item_id}'.")
                sanitized_text = inj.sub("[UNTRUSTED_COMMAND_STRIPPED]", sanitized_text)

        # B. Sensitive Data / PII Redaction
        for pattern, replacement in REDACTION_PATTERNS:
            new_text, count = pattern.subn(replacement, sanitized_text)
            if count > 0:
                total_redactions += count
                sanitized_text = new_text

        # Tokenize source identifier to anonymous reference (sha256 prefix)
        anon_src_ref = f"anon-src-{hashlib.sha256(item_id.encode('utf-8')).hexdigest()[:10]}"

        # C. NLP Sentiment Classification
        tokens = set(re.findall(r"\b\w+\b", sanitized_text.lower()))
        pos_matches = tokens & POSITIVE_WORDS
        neg_matches = tokens & NEGATIVE_WORDS

        pos_count = len(pos_matches)
        neg_count = len(neg_matches)
        denom = pos_count + neg_count or 1
        polarity = round((pos_count - neg_count) / denom, 2)

        if pos_count >= 2 and neg_count >= 2:
            sentiment_label = "MIXED"
        elif polarity > 0.15:
            sentiment_label = "POSITIVE"
        elif polarity < -0.15:
            sentiment_label = "NEGATIVE"
        else:
            sentiment_label = "NEUTRAL"

        sentiment_counts[sentiment_label] += 1
        polarity_sum += polarity

        # Confidence calculation
        if pos_count + neg_count == 0:
            confidence = 0.50
        else:
            confidence = min(0.95, round(0.60 + (min(pos_count + neg_count, 6) * 0.06), 2))

        # D. Objection Extraction
        contrast_words = {"but", "however", "although", "except", "though", "yet"}
        has_contrast = bool(tokens & contrast_words)

        detected_item_objections: list[str] = []
        if sentiment_label != "POSITIVE" or neg_matches or has_contrast:
            for obj_type, trigger_words in OBJECTION_RULES:
                if any(w in sanitized_text.lower() for w in trigger_words) or bool(tokens & trigger_words):
                    detected_item_objections.append(obj_type)
                    all_objections_flat.append(obj_type)

        # E. Urgency / Severity
        critical_words = {"lawsuit", "attorney", "legal", "chargeback", "fraud", "burn", "injury", "hazard", "danger"}
        high_words = {"refund", "unacceptable", "broken", "cancel", "dispute"}
        if any(w in tokens for w in critical_words):
            urgency = "critical"
        elif any(w in tokens for w in high_words):
            urgency = "high"
        elif sentiment_label in ("NEGATIVE", "MIXED") and detected_item_objections:
            urgency = "medium"
        else:
            urgency = "low"

        praise_points = [w for w in pos_matches]
        pain_points = [w for w in neg_matches]

        vector_record = {
            "vector_id": f"vec-{item_id}",
            "source_id_hash": anon_src_ref,
            "source_type": src_type,
            "tenant_id": tenant_id,
            "product_id": item_product,
            "channel": item_channel,
            "sanitized_text": sanitized_text,
            "sentiment_label": sentiment_label,
            "polarity": polarity,
            "confidence": confidence,
            "topics": list(detected_item_objections),
            "intent": "complaint" if detected_item_objections else ("inquiry" if "?" in sanitized_text else "general_feedback"),
            "urgency": urgency,
            "detected_objections": detected_item_objections,
            "pain_points": pain_points,
            "praise_points": praise_points,
            "provenance": {
                "verified_by": "S_PARSE",
                "task_id": task_id,
                "tenant_id": tenant_id,
                "sanitized": True,
            },
        }
        sentiment_vectors.append(vector_record)

    total_items = len(sentiment_vectors)
    avg_polarity = round(polarity_sum / total_items, 2) if total_items > 0 else 0.0

    if total_items == 0:
        primary_sentiment = "neutral"
    elif sentiment_counts["NEGATIVE"] > sentiment_counts["POSITIVE"]:
        primary_sentiment = "negative"
    elif sentiment_counts["POSITIVE"] > sentiment_counts["NEGATIVE"]:
        primary_sentiment = "positive"
    elif sentiment_counts["MIXED"] > 0:
        primary_sentiment = "mixed"
    else:
        primary_sentiment = "neutral"

    # Aggregate recurring objection profiles
    objection_profiles: list[dict[str, Any]] = []
    unique_objection_types = sorted(list(set(all_objections_flat)))

    for obj_type in unique_objection_types:
        matching_vectors = [v for v in sentiment_vectors if obj_type in v["detected_objections"]]
        freq = len(matching_vectors)
        evidence_refs = [v["source_id_hash"] for v in matching_vectors]
        affected_prods = list({v["product_id"] for v in matching_vectors if v["product_id"]})
        affected_chans = list({v["channel"] for v in matching_vectors if v["channel"]})

        obj_sentiments = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0, "MIXED": 0}
        has_critical = False
        has_high = False
        for v in matching_vectors:
            obj_sentiments[v["sentiment_label"]] += 1
            if v["urgency"] == "critical":
                has_critical = True
            elif v["urgency"] == "high":
                has_high = True

        if has_critical or freq >= 4:
            severity = "critical" if has_critical else "high"
        elif has_high or freq >= 2:
            severity = "medium"
        else:
            severity = "low"

        theme_names = {
            "fulfillment_delay": "Logistics and Delivery Latency",
            "price_sensitivity": "Pricing and Perceived Value Objections",
            "customer_service_latency": "Support Responsiveness and Resolution Latency",
            "product_quality_defect": "Product Defects and Material Failures",
            "usability_complexity": "Product Complexity and User Experience Friction",
            "missing_feature": "Functional Gaps and Missing Capabilities",
        }
        normalized_theme = theme_names.get(obj_type, obj_type.replace("_", " ").title())

        objection_profiles.append({
            "objection_id": f"obj-{obj_type}",
            "objection_type": obj_type,
            "normalized_theme": normalized_theme,
            "frequency": freq,
            "affected_products": affected_prods,
            "affected_channels": affected_chans,
            "sentiment_distribution": obj_sentiments,
            "representative_evidence_refs": evidence_refs[:5],
            "confidence": round(min(0.95, 0.70 + (freq * 0.05)), 2),
            "severity": severity,
            "trend": "increasing" if freq >= 3 else "stable",
            "unresolved_ambiguity": [],
            "provenance": {
                "verified_by": "S_PARSE",
                "task_id": task_id,
                "tenant_id": tenant_id,
            },
        })

    analysis_result_dict = {
        "analysis_id": f"voice-{task_id}",
        "tenant_id": tenant_id,
        "product_id": product_id,
        "total_items_analyzed": total_items,
        "average_polarity": avg_polarity,
        "sentiment_breakdown": sentiment_counts,
        "sentiment_vectors": sentiment_vectors,
        "objection_profiles": objection_profiles,
        "warnings": warnings,
        "anonymization_stats": {
            "total_redactions": total_redactions,
            "anonymized_source_references": total_items,
        },
        "provenance": {
            "verified_by": "S_PARSE",
            "task_id": task_id,
            "tenant_id": tenant_id,
        },
    }

    feedback_summary = (
        f"Analyzed {total_items} feedback items with average polarity {avg_polarity:.2f} ({primary_sentiment}). "
        f"Objections identified: {', '.join(unique_objection_types) or 'None'}. "
        f"Redacted sensitive fields: {total_redactions}."
    )

    return {
        "status": "success",
        "task_id": task_id,
        "sentiment_polarity": f"{avg_polarity:.2f}",
        "primary_sentiment": primary_sentiment,
        "objections": json.dumps(unique_objection_types or ["none_detected"]),
        "feedback_summary": feedback_summary,
        "customer_voice_analysis": json.dumps(analysis_result_dict),
        "objection_profiles": json.dumps(objection_profiles),
        "sentiment_vectors": json.dumps(sentiment_vectors),
    }
