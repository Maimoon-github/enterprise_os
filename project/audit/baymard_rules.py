# pyright: reportMissingImports=false
"""Baymard Institute CRO Heuristics Engine for E-Commerce Checkout Flows (TSK-04).
Encodes checkout usability guidelines to flag high-friction drop-off points.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class BaymardRuleViolation(BaseModel):
    """Structured violation record for an identified Baymard checkout issue."""

    rule_id: str
    category: str
    title: str
    description: str
    severity: str = "high"  # "critical", "high", "medium"
    evidence: str = ""


class BaymardEvaluationResult(BaseModel):
    """Aggregate result from executing Baymard CRO heuristics across DOM and metadata."""

    violations: List[BaymardRuleViolation] = Field(default_factory=list)
    baymard_issues: List[str] = Field(default_factory=list)
    friction_score: float = 0.0  # 0.0 (frictionless) to 100.0 (severe friction)
    passed_rules: List[str] = Field(default_factory=list)


class BaymardHeuristicsEngine:
    """Automated evaluation engine for Baymard Institute checkout usability heuristics."""

    def __init__(self):
        # Known trust badge indicators
        self.trust_keywords = [
            "secure checkout",
            "ssl",
            "money-back guarantee",
            "money back guarantee",
            "satisfaction guaranteed",
            "trusted store",
            "mcafee",
            "norton",
            "verisign",
            "pci compliant",
            "30-day return",
            "free returns",
            "encrypted",
        ]

    def evaluate(self, dom_markdown: str, html_content: str = "") -> BaymardEvaluationResult:
        """Run all Baymard checkout friction rules against DOM markdown and HTML content."""
        violations: List[BaymardRuleViolation] = []
        passed: List[str] = []

        combined_text = f"{dom_markdown}\n{html_content}".lower()

        # Rule 1: Forced Account Registration / Missing Guest Checkout
        # Baymard: 34% of shoppers abandon carts if forced to create an account.
        has_forced_reg = bool(
            re.search(
                r"create an account to continue|must register|mandatory account|registration required|please sign up to checkout",
                combined_text,
            )
        )
        has_guest_checkout = bool(
            re.search(
                r"guest checkout|checkout as guest|continue as guest|proceed as guest",
                combined_text,
            )
        )

        if has_forced_reg or (
            ("sign in" in combined_text or "create account" in combined_text)
            and not has_guest_checkout
            and "checkout" in combined_text
        ):
            violations.append(
                BaymardRuleViolation(
                    rule_id="BAYMARD-01",
                    category="Account Creation",
                    title="Forced Account Creation / Missing Guest Checkout",
                    description="Mandatory registration enforced during checkout without a prominent guest checkout option.",
                    severity="critical",
                    evidence="Forced account creation detected without guest checkout alternative.",
                )
            )
        else:
            passed.append("BAYMARD-01")

        # Rule 2: Hidden Shipping Costs & Surprise Fees
        # Baymard: 48% abandon carts because extra costs (shipping, tax, fees) were too high or disclosed too late.
        has_hidden_shipping = bool(
            re.search(
                r"shipping calculated at next step|shipping calculated at checkout|taxes and fees calculated at payment|additional fees apply|undisclosed shipping",
                combined_text,
            )
        )
        has_shipping_calculator = bool(
            re.search(
                r"free shipping|shipping calculator|estimate shipping|standard shipping \$",
                combined_text,
            )
        )

        if has_hidden_shipping and not has_shipping_calculator:
            violations.append(
                BaymardRuleViolation(
                    rule_id="BAYMARD-02",
                    category="Pricing & Fees",
                    title="Hidden Shipping Costs Disclosed Late",
                    description="Shipping costs and extra fees are hidden until final payment steps rather than upfront calculation.",
                    severity="critical",
                    evidence="Late disclosure of shipping fees detected without upfront shipping calculator.",
                )
            )
        else:
            passed.append("BAYMARD-02")

        # Rule 3: Missing Trust Signals & Security Badges in Checkout Viewport
        # Baymard: 18% abandon carts due to lack of trust with credit card information.
        has_trust_signal = any(kw in combined_text for kw in self.trust_keywords)
        if not has_trust_signal and ("checkout" in combined_text or "payment" in combined_text or "cart" in combined_text):
            violations.append(
                BaymardRuleViolation(
                    rule_id="BAYMARD-03",
                    category="Trust & Security",
                    title="Missing Trust Signals and Security Seals",
                    description="Storefront checkout lacks visual security badges, SSL trust seals, or clear return guarantees.",
                    severity="high",
                    evidence="Zero trust seals or security guarantees detected in checkout flow.",
                )
            )
        else:
            passed.append("BAYMARD-03")

        # Rule 4: Checkout Form Friction & Excessive Input Fields
        # Baymard: Ideal checkout has ~6-8 fields; >12 causes cognitive friction.
        input_count = len(re.findall(r"<input", html_content, re.IGNORECASE))
        if input_count == 0:
            # Fallback markdown detection for form fields
            input_count = len(re.findall(r"\[\s*\]|___|input:", dom_markdown, re.IGNORECASE))

        if input_count > 12:
            violations.append(
                BaymardRuleViolation(
                    rule_id="BAYMARD-04",
                    category="Form Usability",
                    title="Excessive Checkout Form Fields",
                    description=f"Detected {input_count} form fields. Exceeds recommended 8-field usability threshold.",
                    severity="medium",
                    evidence=f"Form field count: {input_count}",
                )
            )
        else:
            passed.append("BAYMARD-04")

        # Rule 5: Distracting Promo / Coupon Code Prompts
        # Baymard: Prominent empty coupon boxes trigger coupon searching and cart abandonment.
        has_prominent_coupon = bool(
            re.search(
                r"enter promo code|have a coupon\?|apply discount code|enter coupon code",
                combined_text,
            )
        )
        has_coupon_collapsed = bool(
            re.search(
                r"have a code\?|promo code \(optional\)|expand coupon",
                combined_text,
            )
        )
        if has_prominent_coupon and not has_coupon_collapsed:
            violations.append(
                BaymardRuleViolation(
                    rule_id="BAYMARD-05",
                    category="Checkout Flow",
                    title="Prominent Empty Coupon Field Friction",
                    description="Overly prominent promo code input causes shoppers to exit checkout looking for external discounts.",
                    severity="medium",
                    evidence="Uncollapsed promo code box detected in checkout sequence.",
                )
            )
        else:
            passed.append("BAYMARD-05")

        # Calculate friction score (0 to 100)
        weight_map = {"critical": 35.0, "high": 20.0, "medium": 10.0}
        total_friction = sum(weight_map.get(v.severity, 10.0) for v in violations)
        friction_score = min(100.0, total_friction)

        issue_strings = [f"[{v.rule_id}] {v.title}: {v.description}" for v in violations]

        return BaymardEvaluationResult(
            violations=violations,
            baymard_issues=issue_strings,
            friction_score=friction_score,
            passed_rules=passed,
        )


def evaluate_baymard_rules(dom_markdown: str, html_content: str = "") -> List[str]:
    """Helper returning human-readable Baymard issue strings for state metrics."""
    engine = BaymardHeuristicsEngine()
    result = engine.evaluate(dom_markdown, html_content)
    return result.baymard_issues
