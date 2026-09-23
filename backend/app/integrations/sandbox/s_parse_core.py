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


# ============================================================================
# CV-04 Discovery and Sanitization Core Functions
# ============================================================================

def detect_language(text: str) -> tuple[str, str, float]:
    """Deterministic language identification without external APIs or translation.

    Returns (locale_code, detector_identifier, confidence).
    If confidence < 0.60 or characters are unidentifiable, returns 'unknown' or 'not_assessed'.
    """
    clean = text.strip()
    if not clean:
        return "unknown", "regex_char_classifier_v1", 0.0

    # Common European char distributions
    total_alpha = sum(1 for c in clean if c.isalpha())
    if total_alpha < 3:
        return "not_assessed", "regex_char_classifier_v1", 0.0

    # German markers
    german_markers = {"der", "die", "das", "und", "ist", "nicht", "ein", "eine", "mit", "für", "sehr", "gut"}
    french_markers = {"le", "la", "les", "et", "est", "un", "une", "avec", "pour", "très", "bien", "pas"}
    spanish_markers = {"el", "la", "los", "las", "y", "es", "un", "una", "con", "para", "muy", "bien", "no"}

    words = set(re.findall(r"\b\w+\b", clean.lower()))
    if len(words & german_markers) >= 2:
        return "de", "regex_char_classifier_v1", 0.85
    if len(words & french_markers) >= 2:
        return "fr", "regex_char_classifier_v1", 0.85
    if len(words & spanish_markers) >= 2:
        return "es", "regex_char_classifier_v1", 0.85

    # Check for non-ASCII scripts
    has_cyrillic = bool(re.search(r"[\u0400-\u04FF]", clean))
    if has_cyrillic:
        return "ru", "regex_char_classifier_v1", 0.90

    has_cjk = bool(re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", clean))
    if has_cjk:
        return "zh", "regex_char_classifier_v1", 0.90

    # Default ASCII / Latin check
    ascii_ratio = sum(1 for c in clean if ord(c) < 128) / len(clean)
    if ascii_ratio >= 0.8:
        return "en", "regex_char_classifier_v1", 0.95

    return "unknown", "regex_char_classifier_v1", 0.40


def sanitize_text_and_redact(
    raw_text: str,
) -> tuple[str, dict[str, int], bool]:
    """Execute deterministic PII scrubbing and prompt-injection detection.

    Returns (sanitized_text, redaction_counts, injection_flagged).
    """
    sanitized = raw_text
    injection_flagged = False
    for inj in INJECTION_PATTERNS:
        if inj.search(sanitized):
            injection_flagged = True
            sanitized = inj.sub("[UNTRUSTED_COMMAND_STRIPPED]", sanitized)

    redaction_summary: dict[str, int] = {}
    type_names = [
        "EMAIL",
        "PHONE",
        "ACCOUNT_NUMBER",
        "IP_ADDRESS",
        "PERSON_NAME",
        "CREDENTIAL",
    ]

    for (pattern, repl), name in zip(REDACTION_PATTERNS, type_names):
        sanitized, count = pattern.subn(repl, sanitized)
        if count > 0:
            redaction_summary[name] = redaction_summary.get(name, 0) + count

    return sanitized, redaction_summary, injection_flagged


def run_discovery_sanitization_pipeline(
    raw_items: list[dict[str, Any]],
    tenant_id: str,
    task_id: str,
    hmac_key: str | None = None,
) -> dict[str, Any]:
    """Full CV-04 Discovery and Sanitization Pipeline.

    Enforces:
    1. Tenant isolation.
    2. Input validation without fallback fabrication.
    3. Separate random opaque record ID from canonical content integrity hash.
    4. Deterministic language detection without fabricated translation.
    5. Deterministic PII redaction and prompt injection isolation.
    6. Deduplication preserving duplicate lineage (canonical + member refs).
    7. Evidence span index generation against sanitized text.
    8. Freeze sanitized corpus and compute immutable bundle hash.
    """
    import hmac

    if not raw_items:
        return {
            "status": "incomplete",
            "reason": "missing_feedback_evidence",
            "records": [],
            "evidence_spans": [],
            "immutable_corpus_hash": hashlib.sha256(b"empty").hexdigest(),
        }

    # Step 1 & 2: Normalize and Scrub
    processed_records: list[dict[str, Any]] = []

    for idx, item in enumerate(raw_items):
        item_tenant = item.get("tenant_id")
        if item_tenant and item_tenant != tenant_id:
            raise ValueError(
                f"Tenant isolation breach in Discovery input: item tenant '{item_tenant}' "
                f"does not match task tenant '{tenant_id}'."
            )

        source_ref = str(item.get("item_id", item.get("source_ref", f"src-{idx + 1}")))
        raw_text = str(item.get("text", item.get("content", item.get("body", ""))))
        source_type = str(item.get("source_type", item.get("type", "feedback")))
        channel = item.get("channel")
        touchpoint = item.get("touchpoint")
        timestamp = item.get("timestamp")
        product_ref = item.get("product_ref", item.get("product_id"))
        explicit_segments = list(item.get("explicit_segment_refs", item.get("segments", [])))
        survey_ref = item.get("survey_methodology_ref")

        # Identity separation:
        # If hmac_key is provided by trusted host, compute HMAC ID; otherwise generate random opaque UUID
        if hmac_key:
            opaque_id = f"rec-{hmac.new(hmac_key.encode('utf-8'), f'{tenant_id}:{source_ref}'.encode('utf-8'), hashlib.sha256).hexdigest()[:16]}"
        else:
            opaque_id = f"rec-{hashlib.sha256(f'{task_id}:{source_ref}:{idx}'.encode('utf-8')).hexdigest()[:16]}"

        # Integrity hash (canonical raw content hash)
        record_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        # Language Detection
        detected_locale, detector_ver, conf = detect_language(raw_text)

        # PII Scrubbing and Injection Flagging
        sanitized_text, redactions, injection_flagged = sanitize_text_and_redact(raw_text)

        processed_records.append({
            "opaque_record_id": opaque_id,
            "record_hash": record_hash,
            "source_ref": source_ref,
            "source_type": source_type,
            "channel": channel,
            "touchpoint": touchpoint,
            "timestamp": timestamp,
            "locale": detected_locale,
            "product_ref": product_ref,
            "explicit_segment_refs": explicit_segments,
            "sanitized_text": sanitized_text,
            "redaction_summary": redactions,
            "injection_flagged": injection_flagged,
            "dedupe_group": None,
            "duplicate_members": [],
            "survey_methodology_ref": survey_ref,
            "provenance_ref": f"prov:{task_id}:discovery:{opaque_id}",
            "_clean_norm": " ".join(sanitized_text.lower().split()),
        })

    # Step 3: Deduplication with full lineage preservation
    seen_hashes: dict[str, dict[str, Any]] = {}
    deduped_records: list[dict[str, Any]] = []

    for r in processed_records:
        norm_key = hashlib.sha256(r["_clean_norm"].encode("utf-8")).hexdigest()
        if norm_key in seen_hashes:
            canonical = seen_hashes[norm_key]
            canonical["dedupe_group"] = canonical["dedupe_group"] or f"dedupe-{norm_key[:12]}"
            canonical["duplicate_members"].append(r["source_ref"])
        else:
            seen_hashes[norm_key] = r
            deduped_records.append(r)

    # Clean temporary internal normalization keys
    for r in deduped_records:
        r.pop("_clean_norm", None)

    # Step 4: Evidence Span Indexing on sanitized text
    evidence_spans: list[dict[str, Any]] = []
    for r in deduped_records:
        stext = r["sanitized_text"]
        s_hash = hashlib.sha256(stext.encode("utf-8")).hexdigest()
        # Create full-sentence evidence spans for traceability
        sentences = re.split(r"(?<=[.!?])\s+", stext)
        curr_offset = 0
        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            start = stext.find(s_clean, curr_offset)
            if start == -1:
                start = curr_offset
            end = start + len(s_clean)
            curr_offset = end
            span_hash = hashlib.sha256(s_clean.encode("utf-8")).hexdigest()

            evidence_spans.append({
                "record_id": r["opaque_record_id"],
                "sanitized_text_hash": s_hash,
                "start_offset": start,
                "end_offset": end,
                "span_hash": span_hash,
                "source_ref": r["source_ref"],
                "exact_quote": s_clean,
            })

    # Step 5: Freeze Immutable Corpus Bundle
    canonical_corpus_data = json.dumps(
        {"records": deduped_records, "spans": evidence_spans},
        sort_keys=True,
        default=str,
    )
    corpus_hash = hashlib.sha256(canonical_corpus_data.encode("utf-8")).hexdigest()

    return {
        "status": "success",
        "task_id": task_id,
        "tenant_id": tenant_id,
        "records_count": len(deduped_records),
        "records": deduped_records,
        "evidence_spans": evidence_spans,
        "immutable_corpus_hash": corpus_hash,
    }

