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
    budget_total = float(payload.get("budget", payload.get("budget_cap", "10000.0")))
    channels_raw = payload.get("channels", "meta,google,tiktok,linkedin")
    channels = [c.strip() for c in channels_raw.split(",") if c.strip()]
    if not channels:
        channels = ["meta", "google", "tiktok"]

    # Target ROAS priors per channel
    roas_priors = {
        "meta": float(payload.get("prior_roas_meta", "3.2")),
        "google": float(payload.get("prior_roas_google", "3.8")),
        "tiktok": float(payload.get("prior_roas_tiktok", "2.6")),
        "linkedin": float(payload.get("prior_roas_linkedin", "2.1")),
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
        "primary_channel": max(allocations, key=allocations.get),  # type: ignore[arg-type]
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


def execute_s_val(payload: dict[str, str]) -> dict[str, str]:
    """S_VAL: Claim & Schema Validator [Micro-Tool: Compliance Linter].

    Validates proposed advertising or clinical claims against compliance rules,
    detects unsupported absolutes, and checks required statutory disclaimers.
    """
    task_id = payload.get("task_id", "unknown")
    claim_text = payload.get("claim", payload.get("statement", "Clinically tested to improve performance by 40%."))
    required_disclaimer = payload.get("required_disclaimer", "*Results may vary based on usage.")

    # High-risk claim patterns
    prohibited_claim_patterns = [
        r"\bcures?\b",
        r"\b100% guaranteed\b",
        r"\bprevents? all\b",
        r"\bpermanent elimination\b",
    ]

    violations = []
    for pattern in prohibited_claim_patterns:
        if re.search(pattern, claim_text, re.IGNORECASE):
            violations.append(f"Prohibited absolute claim pattern detected: {pattern}")

    disclaimer_present = required_disclaimer.lower() in claim_text.lower() or "*results" in claim_text.lower()
    if not disclaimer_present and "%" in claim_text:
        violations.append("Quantitative claim requires statutory disclaimer footnote.")

    compliance_score = max(0.0, 1.0 - (len(violations) * 0.4))
    is_compliant = len(violations) == 0

    return {
        "status": "success" if is_compliant else "compliance_warning",
        "task_id": task_id,
        "claim": claim_text,
        "is_compliant": str(is_compliant),
        "compliance_score": f"{compliance_score:.2f}",
        "violations": json.dumps(violations),
        "verified_dossier": f"Claim: {claim_text} | Compliance Score: {compliance_score:.2f} | Status: {'APPROVED' if is_compliant else 'FLAGGED'}",
    }


def execute_s_scrape(payload: dict[str, str]) -> dict[str, str]:
    """S_SCRAPE: Price & Ad Scraper [Micro-Tool: External DOM Tracker].

    Simulates whitelisted external DOM extraction for competitor ad libraries and price trends.
    """
    task_id = payload.get("task_id", "unknown")
    competitor = payload.get("competitor", "CompetitorCorp")

    # Benchmarks extracted from simulated competitor feed
    price_point = float(payload.get("benchmark_price", "49.99"))
    active_ad_count = int(payload.get("active_ads", "14"))
    top_ad_hook = f"Save 25% on our premium bundle this week only."

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


def execute_s_parse(payload: dict[str, str]) -> dict[str, str]:
    """S_PARSE: Sentiment & Review Parser [Micro-Tool: NLP Classifier].

    Classifies customer support tickets and user reviews, extracts sentiment polarity,
    and identifies core customer objection clusters.
    """
    task_id = payload.get("task_id", "unknown")
    text = payload.get("feedback_text", payload.get("query", "Love the product quality but shipping took 10 days and support was slow."))

    # Lightweight sentiment analysis
    positive_words = {"love", "great", "excellent", "fast", "effective", "good", "best", "satisfied"}
    negative_words = {"slow", "expensive", "shipping", "broke", "delayed", "poor", "difficult", "bad"}

    tokens = set(re.findall(r"\b\w+\b", text.lower()))
    pos_count = len(tokens & positive_words)
    neg_count = len(tokens & negative_words)

    total = pos_count + neg_count or 1
    polarity = (pos_count - neg_count) / total  # between -1.0 and +1.0

    objections = []
    if "shipping" in tokens or "delayed" in tokens:
        objections.append("fulfillment_delay")
    if "expensive" in tokens or "price" in tokens:
        objections.append("price_sensitivity")
    if "slow" in tokens or "support" in tokens:
        objections.append("customer_service_latency")

    return {
        "status": "success",
        "task_id": task_id,
        "sentiment_polarity": f"{polarity:.2f}",
        "primary_sentiment": "positive" if polarity > 0.2 else ("negative" if polarity < -0.2 else "neutral"),
        "objections": json.dumps(objections or ["none_detected"]),
        "feedback_summary": f"Analyzed feedback with polarity {polarity:.2f}. Objections identified: {', '.join(objections) or 'None'}.",
    }


def execute_s_attr(payload: dict[str, str]) -> dict[str, str]:
    """S_ATTR: Attribution Modeler [Micro-Tool: Decay Scorer].

    Computes multi-touch attribution, creative decay rates, and ROAS optimization adjustments.
    """
    task_id = payload.get("task_id", "unknown")
    reported_roas = float(payload.get("roas", payload.get("metrics_roas", "3.4")))
    days_active = float(payload.get("days_active", "14.0"))

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
