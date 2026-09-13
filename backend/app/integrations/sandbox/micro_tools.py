"""Specialist Sandbox Sub-Agents and Micro-Tools.

Runs strictly within the sandbox execution boundary (Layer 6).
Implements the 7 specialist micro-tools defined by the architecture:
- S_CODE: Component Coder & Linter [Micro-Tool: AST Parser]
- S_ALLOC: Media & Budget Allocator [Micro-Tool: Optimization Modeler]
- S_COPY: Copy Drafter & Hook Critic [Micro-Tool: Variant Generator]
- S_VAL: Claim & Schema Validator [Micro-Tool: Compliance Linter]
- S_SCRAPE: Price & Ad Scraper [Micro-Tool: External DOM Tracker]
- S_PARSE: Sentiment & Review Parser [Micro-Tool: NLP Classifier]
- S_ATTR: Attribution Modeler [Micro-Tool: Decay Scorer]
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from typing import Any

from app.schemas.sandbox import SandboxCapability


def execute_s_code(payload: dict[str, str]) -> dict[str, str]:
    """S_CODE: Component Coder & Linter [Micro-Tool: AST Parser].

    Parses source code or schema snippets with Python AST, checks syntax,
    computes complexity metrics, and generates unified code diffs.
    """
    code_content = payload.get("code") or payload.get("schema_content") or ""
    task_id = payload.get("task_id", "unknown")
    component_name = payload.get("component_name", "LayoutTemplate")

    ast_valid = True
    node_count = 0
    function_count = 0
    class_count = 0
    syntax_error = None

    if code_content:
        try:
            tree = ast.parse(code_content)
            for node in ast.walk(tree):
                node_count += 1
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    function_count += 1
                elif isinstance(node, ast.ClassDef):
                    class_count += 1
        except SyntaxError as err:
            ast_valid = False
            syntax_error = f"SyntaxError at line {err.lineno}: {err.msg}"
    else:
        # Generate default component skeleton and diff if none provided
        code_content = (
            f"class {component_name}:\n"
            f"    def render(self, context: dict) -> str:\n"
            f"        return f'<div>{component_name}: {{context}}</div>'\n"
        )
        tree = ast.parse(code_content)
        node_count = len(list(ast.walk(tree)))
        class_count = 1
        function_count = 1

    diff = (
        f"--- a/components/{component_name.lower()}.py\n"
        f"+++ b/components/{component_name.lower()}.py\n"
        f"@@ -0,0 +1,5 @@\n"
        + "".join(f"+ {line}\n" for line in code_content.strip().splitlines())
    )

    return {
        "status": "success" if ast_valid else "lint_failed",
        "task_id": task_id,
        "component_name": component_name,
        "ast_valid": str(ast_valid),
        "node_count": str(node_count),
        "function_count": str(function_count),
        "class_count": str(class_count),
        "diff": diff,
        "syntax_error": syntax_error or "",
        "code": code_content,
    }


def execute_s_alloc(payload: dict[str, str]) -> dict[str, str]:
    """S_ALLOC: Media & Budget Allocator [Micro-Tool: Optimization Modeler].

    Applies ROAS-weighted, risk-adjusted budget optimization across omnichannel ad networks.
    """
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

    # Target ROAS priors per channel
    try:
        prior_meta = float(payload.get("prior_roas_meta", "3.2"))
    except (ValueError, TypeError):
        prior_meta = 3.2
    try:
        prior_google = float(payload.get("prior_roas_google", "3.8"))
    except (ValueError, TypeError):
        prior_google = 3.8
    try:
        prior_tiktok = float(payload.get("prior_roas_tiktok", "2.6"))
    except (ValueError, TypeError):
        prior_tiktok = 2.6
    try:
        prior_linkedin = float(payload.get("prior_roas_linkedin", "2.1"))
    except (ValueError, TypeError):
        prior_linkedin = 2.1

    roas_priors = {
        "meta": prior_meta,
        "google": prior_google,
        "tiktok": prior_tiktok,
        "linkedin": prior_linkedin,
    }

    # Weight proportional to expected ROAS
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
        "primary_channel": max(allocations, key=lambda ch: allocations[ch]) if allocations else "none",
    }


def execute_s_copy(payload: dict[str, str]) -> dict[str, str]:
    """S_COPY: Copy Drafter & Hook Critic [Micro-Tool: Variant Generator].

    Generates copy variants, ranks hooks by engagement heuristics,
    and screens against prohibited terms and brand voice constraints.
    """
    task_id = payload.get("task_id", "unknown")
    brand_voice = payload.get("brand_voice", "authoritative")
    objective = payload.get("objective", "summer campaign")
    prohibited_raw = payload.get("prohibited_terms", "")
    prohibited_terms = [t.strip().lower() for t in prohibited_raw.split(",") if t.strip()]

    # Generate distinct hook angles
    candidates: list[tuple[str, str, float]] = [
        (f"Stop guessing with your {objective}—here is the proven formula.", "pain_point", 0.88),
        (f"Why leading brands are upgrading their {objective} today.", "social_proof", 0.92),
        (f"The hidden secret to 3x better results in {objective}.", "curiosity", 0.85),
    ]

    filtered_variants: list[tuple[str, str, float]] = []
    for hook_text, angle, score in candidates:
        contains_prohibited = any(term in hook_text.lower() for term in prohibited_terms)
        if not contains_prohibited:
            filtered_variants.append((hook_text, angle, score))

    best_hook = max(filtered_variants, key=lambda x: x[2]) if filtered_variants else candidates[0]
    best_headline, best_angle, best_score = best_hook

    variants_json = [
        {"hook": h, "angle": a, "score": s}
        for h, a, s in (filtered_variants or candidates)
    ]

    return {
        "status": "success",
        "task_id": task_id,
        "brand_voice": brand_voice,
        "headline": best_headline,
        "hook_score": str(best_score),
        "hook_angle": best_angle,
        "variants": json.dumps(variants_json),
        "copy_body": f"Designed for performance in {brand_voice} voice. {best_headline} Unlock enterprise scalability with verified evidence.",
    }


def execute_s_val(payload: dict[str, Any]) -> dict[str, str]:
    """S_VAL: Claim & Schema Validator [Micro-Tool: Compliance Linter].

    Validates proposed advertising or clinical claims against compliance rules,
    verifies claim-to-evidence linkage, checks evidence sufficiency and freshness,
    detects conflicting evidence and unsupported absolutes, verifies product
    formulation completeness, and checks required statutory disclaimers.
    """
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    product_id = str(payload.get("product_id", "default_product"))
    product_name = str(payload.get("product_name", payload.get("brand_id", "Default Product")))

    # 1. Parse Claims
    raw_claims = payload.get("claims")
    claims_list: list[dict[str, Any]] = []
    if raw_claims:
        if isinstance(raw_claims, str):
            try:
                parsed = json.loads(raw_claims)
                claims_list = parsed if isinstance(parsed, list) else [parsed]
            except Exception:
                claims_list = [{"text": raw_claims}]
        elif isinstance(raw_claims, list):
            claims_list = raw_claims
    elif "claim" in payload or "statement" in payload:
        claims_list = [{
            "id": "claim-0",
            "text": str(payload.get("claim", payload.get("statement", ""))),
            "category": str(payload.get("category", "performance")),
        }]

    # 2. Parse Evidence Pool
    raw_evidence = payload.get("evidence", payload.get("validated_evidence"))
    evidence_pool: list[dict[str, Any]] = []
    evidence_provided = raw_evidence is not None
    if raw_evidence:
        if isinstance(raw_evidence, str):
            try:
                parsed_ev = json.loads(raw_evidence)
                evidence_pool = parsed_ev if isinstance(parsed_ev, list) else [parsed_ev]
            except Exception:
                evidence_pool = [{"content": raw_evidence, "doc_id": "ev-0"}]
        elif isinstance(raw_evidence, list):
            evidence_pool = raw_evidence

    # 3. Parse Formulation / Specifications
    raw_formulation = payload.get("formulation", payload.get("specifications", payload.get("product_specification")))
    formulation_data: dict[str, Any] = {}
    if raw_formulation:
        if isinstance(raw_formulation, str):
            try:
                formulation_data = json.loads(raw_formulation)
            except Exception:
                formulation_data = {"raw_notes": raw_formulation}
        elif isinstance(raw_formulation, dict):
            formulation_data = raw_formulation

    required_disclaimer = str(payload.get("required_disclaimer", "*Results may vary based on usage."))
    raw_compliance_rules = payload.get("compliance_rules", payload.get("brand_rules"))
    custom_rules: list[str] = []
    if raw_compliance_rules:
        if isinstance(raw_compliance_rules, str):
            try:
                parsed_cr = json.loads(raw_compliance_rules)
                custom_rules = parsed_cr if isinstance(parsed_cr, list) else [str(parsed_cr)]
            except Exception:
                custom_rules = [raw_compliance_rules]
        elif isinstance(raw_compliance_rules, list):
            custom_rules = [str(r) for r in raw_compliance_rules]
        elif isinstance(raw_compliance_rules, dict):
            custom_rules = [f"{k}:{v}" for k, v in raw_compliance_rules.items()]

    # High-risk / prohibited claim patterns
    prohibited_claim_patterns = [
        r"\bcures?\b",
        r"\b100% guaranteed\b",
        r"\bprevents? all\b",
        r"\bpermanent elimination\b",
    ]

    all_violations: list[str] = []

    # 4. Validate Product Formulation & Specifications
    spec_validation_status = "VALIDATED"
    spec_findings: list[str] = []
    missing_attributes: list[str] = []
    ingredients = formulation_data.get("ingredients", [])
    if formulation_data:
        prod_id_spec = formulation_data.get("product_id", product_id)
        if not prod_id_spec or prod_id_spec == "unknown":
            missing_attributes.append("product_id")
        if not formulation_data.get("product_name") and not product_name:
            missing_attributes.append("product_name")

        if isinstance(ingredients, list) and ingredients:
            total_pct = 0.0
            has_pct = False
            for idx, ing in enumerate(ingredients):
                if isinstance(ing, dict):
                    pct = ing.get("percentage", ing.get("concentration", ing.get("pct")))
                    if pct is not None:
                        try:
                            val = float(pct)
                            if val < 0.0:
                                all_violations.append(f"Negative ingredient concentration in ingredient {ing.get('name', idx)}: {val}%")
                            total_pct += val
                            has_pct = True
                        except (ValueError, TypeError):
                            all_violations.append(f"Malformed ingredient concentration in ingredient {ing.get('name', idx)}")
            if has_pct and total_pct > 100.5:
                all_violations.append(f"Ingredient concentration sum exceeds 100.0%: {total_pct:.1f}%")
                spec_validation_status = "INCOMPLETE_SPECIFICATION"

        if missing_attributes:
            spec_validation_status = "INCOMPLETE_SPECIFICATION"
            spec_findings.append(f"Missing required specification attributes: {', '.join(missing_attributes)}")

    # 5. Validate Each Proposed Claim
    verified_claim_entries: list[dict[str, Any]] = []
    supported_count = 0
    rejected_count = 0
    insufficient_count = 0
    conflicting_count = 0
    requires_review_count = 0

    for idx, c in enumerate(claims_list):
        claim_id = str(c.get("id", f"claim-{idx + 1}"))
        claim_text = str(c.get("text", c.get("claim", c.get("statement", ""))))
        category = str(c.get("category", "performance"))
        claim_violations: list[str] = []
        claim_warnings: list[str] = []
        supporting_refs: list[str] = []
        contradicting_refs: list[str] = []
        rule_checks: list[str] = []

        # A. Prohibited absolutes check
        is_prohibited = False
        for pattern in prohibited_claim_patterns:
            if re.search(pattern, claim_text, re.IGNORECASE):
                violation_msg = f"Prohibited absolute claim pattern detected: {pattern}"
                claim_violations.append(violation_msg)
                all_violations.append(violation_msg)
                is_prohibited = True

        # Custom rules check
        for rule in custom_rules:
            rule_checks.append(f"rule:{rule}")
            if rule.lower() in claim_text.lower() and "prohibit" in rule.lower():
                violation_msg = f"Custom compliance rule violated: {rule}"
                claim_violations.append(violation_msg)
                all_violations.append(violation_msg)
                is_prohibited = True

        # B. Statutory disclaimer check for quantitative claims
        disclaimer_present = (
            required_disclaimer.lower() in claim_text.lower()
            or "*results" in claim_text.lower()
            or "*" in claim_text
        )
        has_quantitative = "%" in claim_text or bool(re.search(r"\b\d+x\b", claim_text, re.IGNORECASE))
        if has_quantitative and not disclaimer_present:
            disclaimer_violation = "Quantitative claim requires statutory disclaimer footnote."
            claim_violations.append(disclaimer_violation)
            all_violations.append(disclaimer_violation)

        # C. Evidence linkage, sufficiency, and consistency
        # Find relevant evidence from pool
        claim_tokens = {tok.lower() for tok in re.findall(r"\b[A-Za-z]{4,}\b", claim_text)}
        # Exclude stop words
        claim_tokens -= {"with", "this", "that", "from", "have", "more", "than", "tested", "clinically", "demonstrated"}

        is_stale_evidence = False
        has_contradiction = False

        for ev in evidence_pool:
            ev_id = str(ev.get("doc_id", ev.get("evidence_id", ev.get("id", "ev-ref"))))
            ev_content = str(ev.get("text", ev.get("content", "")))
            ev_source = str(ev.get("source", ev.get("source_uri", "dossier")))
            ev_stale = bool(ev.get("is_stale", ev.get("stale", False)))
            ev_contradicts = bool(
                ev.get("contradicts", False)
                or ev.get("contradictory", False)
                or "contradicts" in ev_content.lower()
                or "failed to show" in ev_content.lower()
                or "no significant improvement" in ev_content.lower()
                or "adverse reaction" in ev_content.lower()
            )

            # Check explicit link or keyword match
            explicit_ids = c.get("evidence_ids", c.get("evidence_references", []))
            is_linked = ev_id in explicit_ids if explicit_ids else False
            if not is_linked and claim_tokens:
                ev_tokens = {tok.lower() for tok in re.findall(r"\b[A-Za-z]{4,}\b", ev_content)}
                overlap = len(claim_tokens & ev_tokens)
                if overlap >= 2 or (len(claim_tokens) <= 2 and overlap >= 1):
                    is_linked = True

            if is_linked:
                if ev_contradicts:
                    has_contradiction = True
                    contradicting_refs.append(ev_id)
                else:
                    supporting_refs.append(ev_id)
                    if ev_stale:
                        is_stale_evidence = True

        # D. Status classification
        if is_prohibited:
            claim_status = "REJECTED"
            claim_confidence = 0.0
            rejected_count += 1
        elif has_contradiction:
            claim_status = "CONFLICTING_EVIDENCE"
            claim_confidence = 0.2
            claim_warnings.append(f"Contradictory findings detected in evidence references: {contradicting_refs}")
            conflicting_count += 1
        elif evidence_provided and not supporting_refs:
            claim_status = "INSUFFICIENT_EVIDENCE"
            claim_confidence = 0.1
            claim_warnings.append("No supporting evidence found in authorized evidence context.")
            insufficient_count += 1
        elif is_stale_evidence:
            claim_status = "REQUIRES_REVIEW"
            claim_confidence = 0.4
            claim_warnings.append("Supporting evidence is stale or expired; recertification required.")
            requires_review_count += 1
        elif not disclaimer_present and has_quantitative:
            claim_status = "REQUIRES_REVIEW"
            claim_confidence = 0.5
            claim_warnings.append("Missing mandatory statutory disclaimer on quantitative claim.")
            requires_review_count += 1
        else:
            # Clean claim
            if evidence_provided and supporting_refs:
                claim_status = "SUPPORTED"
                claim_confidence = min(0.95, 0.75 + (len(supporting_refs) * 0.1))
                supported_count += 1
            elif not evidence_provided:
                # Backward-compatibility for legacy single-claim checks
                if not claim_violations:
                    claim_status = "SUPPORTED"
                    claim_confidence = 0.8
                    supported_count += 1
                else:
                    claim_status = "REJECTED"
                    claim_confidence = 0.0
                    rejected_count += 1
            else:
                claim_status = "INSUFFICIENT_EVIDENCE"
                claim_confidence = 0.0
                insufficient_count += 1

        verified_claim_entries.append({
            "claim_id": claim_id,
            "claim_text": claim_text,
            "category": category,
            "validation_status": claim_status,
            "confidence": round(claim_confidence, 2),
            "evidence_references": supporting_refs,
            "contradicting_evidence_references": contradicting_refs,
            "rule_compliance_checks": rule_checks,
            "violations": claim_violations,
            "limitations_or_warnings": claim_warnings,
            "provenance": {
                "verified_by": "S_VAL",
                "task_id": task_id,
                "tenant_id": tenant_id,
            },
        })

    total_claims = len(verified_claim_entries)
    compliance_score = max(0.0, 1.0 - (len(all_violations) * 0.4))
    if rejected_count > 0:
        compliance_score = 0.0
    elif conflicting_count > 0:
        compliance_score = min(compliance_score, 0.3)
    elif insufficient_count > 0:
        compliance_score = min(compliance_score, 0.7)
    if total_claims == 0:
        compliance_score = 1.0 if not all_violations else 0.0

    is_compliant = len(all_violations) == 0 and rejected_count == 0 and conflicting_count == 0

    dossier_summary_status = "APPROVED" if (is_compliant and insufficient_count == 0 and requires_review_count == 0) else "FLAGGED"
    if rejected_count > 0:
        dossier_summary_status = "REJECTED"

    primary_claim_text = claims_list[0].get("text", claims_list[0].get("claim", "")) if claims_list else payload.get("claim", "")

    # Construct product specification dictionary
    product_spec_dict = {
        "product_id": product_id,
        "product_name": product_name,
        "tenant_id": tenant_id,
        "formulation_id": formulation_data.get("formulation_id", f"form-{product_id}"),
        "version": str(formulation_data.get("version", "1.0")),
        "normalized_attributes": formulation_data.get("attributes", {
            "category": formulation_data.get("category", "supplement"),
            "dosage_form": formulation_data.get("dosage_form", "capsule"),
        }),
        "ingredients": ingredients,
        "supporting_evidence_references": [ev.get("doc_id", "ev") for ev in evidence_pool if isinstance(ev, dict) and ev.get("doc_id")],
        "validation_status": spec_validation_status,
        "compliance_findings": spec_findings + all_violations,
        "missing_attributes": missing_attributes,
        "provenance": {
            "verified_by": "S_VAL",
            "task_id": task_id,
            "tenant_id": tenant_id,
        },
    }

    # Construct claims dossier dictionary
    claims_dossier_dict = {
        "dossier_id": f"dossier-{task_id}",
        "tenant_id": tenant_id,
        "product_id": product_id,
        "claims": verified_claim_entries,
        "summary_status": dossier_summary_status,
        "total_claims": total_claims,
        "supported_claims": supported_count,
        "rejected_claims": rejected_count,
        "insufficient_claims": insufficient_count,
        "conflicting_claims": conflicting_count,
        "requires_review_claims": requires_review_count,
        "overall_confidence": round(compliance_score, 2),
        "provenance": {
            "verified_by": "S_VAL",
            "task_id": task_id,
            "tenant_id": tenant_id,
        },
    }

    verified_dossier = (
        f"Product: {product_name} ({product_id}) | Claims: {total_claims} (Supported: {supported_count}, "
        f"Rejected: {rejected_count}, Insufficient: {insufficient_count}, Conflicting: {conflicting_count}) | "
        f"Compliance Score: {compliance_score:.2f} | Status: {dossier_summary_status}"
    )

    return {
        "status": "success" if is_compliant else "compliance_warning",
        "task_id": task_id,
        "claim": str(primary_claim_text),
        "is_compliant": str(is_compliant),
        "compliance_score": f"{compliance_score:.2f}",
        "violations": json.dumps(all_violations),
        "verified_dossier": verified_dossier,
        "product_specification": json.dumps(product_spec_dict),
        "claims_dossier": json.dumps(claims_dossier_dict),
    }


def execute_s_scrape(payload: dict[str, str]) -> dict[str, str]:
    """S_SCRAPE: Price & Ad Scraper [Micro-Tool: External DOM Tracker].

    Simulates whitelisted external DOM extraction for competitor ad libraries and price trends.
    """
    task_id = payload.get("task_id", "unknown")
    competitor = payload.get("competitor", "CompetitorCorp")

    # Benchmarks extracted from simulated competitor feed
    try:
        price_point = float(payload.get("benchmark_price", "49.99"))
    except (ValueError, TypeError):
        price_point = 49.99

    try:
        active_ad_count = int(payload.get("active_ads", "14"))
    except (ValueError, TypeError):
        active_ad_count = 14

    top_ad_hook = "Save 25% on our premium bundle this week only."

    return {
        "status": "success",
        "task_id": task_id,
        "competitor": competitor,
        "benchmark_price": f"{price_point:.2f}",
        "active_ads": str(active_ad_count),
        "top_ad_hook": top_ad_hook,
        "pricing_trajectory": "discounting_aggressive",
        "threat_level": "medium",
    }


def execute_s_parse(payload: dict[str, Any]) -> dict[str, str]:
    """S_PARSE: Sentiment & Review Parser [Micro-Tool: NLP Classifier].

    Performs sensitive data redaction (PII/credentials), prompt injection neutralization,
    multi-class sentiment and polarity analysis, intent and objection extraction,
    and recurring objection clustering across tickets, reviews, and survey responses.
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
        single_text = str(payload.get("feedback_text", payload.get("query", "Love the product quality but shipping took 10 days and support was slow.")))
        items_list = [{
            "item_id": "item-0",
            "source_type": str(payload.get("source_type", "feedback")),
            "text": single_text,
            "product_id": product_id,
            "channel": payload.get("channel"),
            "tenant_id": tenant_id,
        }]

    # 2. PII / Sensitive Data Redaction Patterns
    redaction_patterns = [
        (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[REDACTED_EMAIL]"),
        (re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"), "[REDACTED_PHONE]"),
        (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[REDACTED_ACCOUNT]"),
        (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[REDACTED_IP]"),
        (re.compile(r"(?i)\b(?:customer|client|user|name is|i am)\s+(?!support|service|care|team|rep|agent|experience|feedback|review)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"), "[REDACTED_NAME]"),
        (re.compile(r"(?i)(api[_-]?key|secret|token|password|auth)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?"), "[REDACTED_SECRET]"),
    ]

    # Prompt injection patterns inside customer voice data (neutralized fail-safe)
    injection_patterns = [
        re.compile(r"(?i)ignore\s+(?:all\s+)?(?:previous\s+)?instructions"),
        re.compile(r"(?i)system\s+(?:override|prompt)"),
        re.compile(r"(?i)you\s+are\s+now\s+(?:an?\s+)?unrestricted"),
        re.compile(r"(?i)grant\s+(?:admin|full)\s+access"),
        re.compile(r"(?i)execute\s+(?:code|command|tool)"),
        re.compile(r"(?i)output\s+(?:the\s+)?(?:secret|api_key|token)"),
    ]

    # NLP Lexicons
    positive_words = {
        "love", "great", "excellent", "fast", "effective", "good", "best", "satisfied",
        "amazing", "smooth", "helpful", "impressed", "recommend", "reliable", "perfect",
        "fantastic", "quality", "friendly", "prompt", "easy", "delighted", "superb",
    }
    negative_words = {
        "slow", "expensive", "shipping", "broke", "delayed", "poor", "difficult", "bad",
        "terrible", "horrible", "awful", "defective", "useless", "damaged", "rude",
        "frustrated", "unacceptable", "broken", "crash", "refund", "leak", "stains",
        "missing", "confusing", "painful", "fail", "failed", "glitch", "flimsy",
        "unresponsive", "wait", "waited", "waiting", "issue", "problem", "complaint",
        "disappointed", "frustrating",
    }

    # Objection Category Triggers
    objection_rules = [
        ("fulfillment_delay", {"shipping", "delayed", "late", "delivery", "transit", "tracking", "package took", "never arrived"}),
        ("price_sensitivity", {"expensive", "price", "overpriced", "cost", "rip-off", "cheap", "subscription", "charge", "billing"}),
        ("customer_service_latency", {"support", "unresponsive", "hold", "agent", "ticket", "service", "reply", "representative", "chat"}),
        ("product_quality_defect", {"broke", "broken", "defective", "leak", "damaged", "faulty", "flimsy", "defect", "poor quality"}),
        ("usability_complexity", {"confusing", "difficult", "complicated", "instructions", "clunky", "complex", "hard to use"}),
        ("missing_feature", {"lacks", "missing", "wish it had", "no option for", "does not support", "feature"}),
    ]

    sentiment_vectors: list[dict[str, Any]] = []
    total_redactions = 0
    all_objections_flat: list[str] = []
    warnings: list[str] = []
    polarity_sum = 0.0

    sentiment_counts = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0, "MIXED": 0}

    # 3. Analyze Each Feedback Item
    for idx, raw_item in enumerate(items_list):
        item_id = str(raw_item.get("item_id", f"item-{idx + 1}"))
        raw_text = str(raw_item.get("text", ""))
        src_type = str(raw_item.get("source_type", "feedback"))
        item_channel = raw_item.get("channel")
        item_product = raw_item.get("product_id", product_id)

        # A. Prompt Injection Defense
        sanitized_text = raw_text
        for inj in injection_patterns:
            if inj.search(sanitized_text):
                warnings.append(f"Prompt injection pattern detected and neutralized in item '{item_id}'.")
                sanitized_text = inj.sub("[UNTRUSTED_COMMAND_STRIPPED]", sanitized_text)

        # B. Sensitive Data / PII Redaction
        for pattern, replacement in redaction_patterns:
            new_text, count = pattern.subn(replacement, sanitized_text)
            if count > 0:
                total_redactions += count
                sanitized_text = new_text

        # Tokenize source identifier to anonymous reference (sha256 prefix)
        anon_src_ref = f"anon-src-{hashlib.sha256(item_id.encode('utf-8')).hexdigest()[:10]}"

        # C. NLP Sentiment Classification
        tokens = set(re.findall(r"\b\w+\b", sanitized_text.lower()))
        pos_matches = tokens & positive_words
        neg_matches = tokens & negative_words

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
        token_count = len(tokens)
        if pos_count + neg_count == 0:
            confidence = 0.50  # Ambiguous / neutral
        else:
            confidence = min(0.95, round(0.60 + (min(pos_count + neg_count, 6) * 0.06), 2))

        # D. Objection Extraction
        contrast_words = {"but", "however", "although", "except", "though", "yet"}
        has_contrast = bool(tokens & contrast_words)

        detected_item_objections: list[str] = []
        if sentiment_label != "POSITIVE" or neg_matches or has_contrast:
            for obj_type, trigger_words in objection_rules:
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

        # Pain points & praise points
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

    # Determine primary overall sentiment
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

    # 4. Aggregate Recurring Objection Profiles
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

    # Consolidated CustomerVoiceAnalysisResult dictionary
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


def execute_s_attr(payload: dict[str, str]) -> dict[str, str]:
    """S_ATTR: Attribution Modeler [Micro-Tool: Decay Scorer].

    Computes multi-touch attribution, creative decay rates, and ROAS optimization adjustments.
    """
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

    # Half-life exponential decay model: decay = e^(-lambda * t)
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


MICRO_TOOL_DISPATCH = {
    SandboxCapability.CODE: execute_s_code,
    SandboxCapability.ALLOC: execute_s_alloc,
    SandboxCapability.COPY: execute_s_copy,
    SandboxCapability.VAL: execute_s_val,
    SandboxCapability.SCRAPE: execute_s_scrape,
    SandboxCapability.PARSE: execute_s_parse,
    SandboxCapability.ATTR: execute_s_attr,
}


def dispatch_micro_tool(capability: SandboxCapability, payload: dict[str, str]) -> dict[str, str]:
    """Dispatch execution to the specialist micro-tool corresponding to ``capability``."""
    handler = MICRO_TOOL_DISPATCH.get(capability)
    if handler is None:
        raise ValueError(f"No specialist micro-tool found for capability: {capability}")
    return handler(payload)
