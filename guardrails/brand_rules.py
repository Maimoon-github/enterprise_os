# pyright: reportMissingImports=false
"""Deterministic Brand Compliance and Quality Guardrails (TSK-06).
Validates copy tone polarity, readability grade, forbidden terms, and platform formatting standards.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.state import BrandProfile


class BrandComplianceResult(BaseModel):
    """Result of deterministic brand compliance rule evaluation."""

    is_compliant: bool
    violations: List[str] = Field(default_factory=list)
    readability_score: float = 0.0  # Flesch Reading Ease or ARI
    reading_grade_level: str = "8th Grade"
    detected_forbidden_terms: List[str] = Field(default_factory=list)
    tone_analysis: Dict[str, Any] = Field(default_factory=dict)
    platform_standards: Dict[str, Any] = Field(default_factory=dict)
    feedback: str = ""


class BrandComplianceFilter:
    """Deterministic rule checker enforcing style, tone, readability, and brand constraints."""

    DEFAULT_FORBIDDEN_TERMS = [
        "guaranteed overnight",
        "revolutionary",
        "game-changer",
        "miracle cure",
        "secret trick",
        "cheap",
        "100% risk-free",
        "magic bullet",
        "get rich quick",
        "overnight success",
        "instant results",
        "unmatched quality",
    ]

    PLATFORM_LIMITS = {
        "linkedin": {"max_chars": 3000, "max_emojis": 5, "max_hashtags": 5},
        "twitter": {"max_chars": 280, "max_emojis": 3, "max_hashtags": 2},
        "x": {"max_chars": 280, "max_emojis": 3, "max_hashtags": 2},
        "instagram": {"max_chars": 2200, "max_emojis": 8, "max_hashtags": 10},
        "email": {"max_chars": 15000, "max_emojis": 3, "max_hashtags": 0},
    }

    def __init__(self, additional_forbidden_terms: Optional[List[str]] = None):
        self.forbidden_terms = list(self.DEFAULT_FORBIDDEN_TERMS)
        if additional_forbidden_terms:
            self.forbidden_terms.extend([t.lower() for t in additional_forbidden_terms])

    def validate_copy(
        self,
        copy_text: str,
        brand: Optional[BrandProfile] = None,
        platform: str = "linkedin",
    ) -> BrandComplianceResult:
        """Run all deterministic compliance checks against copy."""
        violations: List[str] = []
        detected_terms: List[str] = []

        # Merge brand-specific forbidden keywords
        brand_forbidden = list(self.forbidden_terms)
        if brand and hasattr(brand, "guidelines") and brand.guidelines:
            custom_terms = brand.guidelines.get("forbidden_terms", [])
            brand_forbidden.extend([t.lower() for t in custom_terms])

        clean_text = copy_text.strip()
        lower_text = clean_text.lower()

        # 1. Forbidden Keywords Check
        for term in brand_forbidden:
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, lower_text):
                detected_terms.append(term)
                violations.append(f"Forbidden term detected: '{term}'. Avoid hype/unsubstantiated buzzwords.")

        # 2. Readability Analysis (Automated Readability Index - ARI)
        words = re.findall(r"\b[A-Za-z0-9'-]+\b", clean_text)
        sentences = [s.strip() for s in re.split(r"(?<!\d)\.(?:\s+|$)|[\n!?]+", clean_text) if s.strip()]
        char_count = sum(len(w) for w in words)

        word_count = max(len(words), 1)
        sentence_count = max(len(sentences), 1)

        # ARI formula: 4.71 * (characters / words) + 0.5 * (words / sentences) - 21.43
        ari = 4.71 * (char_count / word_count) + 0.5 * (word_count / sentence_count) - 21.43
        ari_score = max(1.0, round(ari, 1))

        if ari_score <= 6:
            grade_level = "Elementary (Grade 5-6)"
        elif ari_score <= 10:
            grade_level = "Middle School (Grade 7-9 - Optimal)"
        elif ari_score <= 14:
            grade_level = "High School (Grade 10-12)"
        elif ari_score <= 18:
            grade_level = "Professional (Grade 13-16)"
        else:
            grade_level = "Dense Academic (Grade 18+)"
            violations.append(f"Readability too complex (ARI {ari_score}: {grade_level}). Target grade 7-14 for audience engagement.")

        # 3. Tone & Polarity Analysis
        tone_violations = []
        # Check excessive shouting (all-caps words)
        shouting_words = [w for w in words if len(w) > 3 and w.isupper() and w not in ["HTML", "SaaS", "ROAS", "GA4", "REST", "API", "B2B", "D2C"]]
        if len(shouting_words) >= 3:
            tone_violations.append(f"Excessive capitalization detected: {shouting_words[:3]}. Violates professional tone.")

        # Check aggressive punctuation (multiple exclamation marks)
        if re.search(r"!{2,}", clean_text):
            tone_violations.append("Multiple consecutive exclamation marks detected (e.g. '!!'). Violates authoritative brand guidelines.")

        violations.extend(tone_violations)

        tone_analysis = {
            "tone_profile": brand.tone_of_voice if brand else ["Authoritative", "Empathetic"],
            "shouting_count": len(shouting_words),
            "reading_ease": "Good" if ari_score <= 12 else "Complex",
        }

        # 4. Platform Formatting Standards
        platform_key = platform.lower()
        limits = self.PLATFORM_LIMITS.get(platform_key, self.PLATFORM_LIMITS["linkedin"])

        char_len = len(clean_text)
        if char_len > limits["max_chars"]:
            violations.append(f"Platform character limit exceeded: {char_len} > {limits['max_chars']} for {platform}.")

        # Emoji count check (Unicode emojis)
        emojis = re.findall(r"[\U00010000-\U0010ffff]", clean_text)
        if len(emojis) > limits["max_emojis"]:
            violations.append(f"Excessive emoji usage: {len(emojis)} emojis exceed limit of {limits['max_emojis']} for {platform}.")

        # Hashtag check
        hashtags = re.findall(r"#\w+", clean_text)
        if len(hashtags) > limits["max_hashtags"]:
            violations.append(f"Excessive hashtags: {len(hashtags)} exceed platform maximum of {limits['max_hashtags']} for {platform}.")

        platform_standards = {
            "platform": platform,
            "character_count": char_len,
            "emoji_count": len(emojis),
            "hashtag_count": len(hashtags),
        }

        is_compliant = len(violations) == 0
        feedback = (
            "Copy conforms with all deterministic brand rules and platform standards."
            if is_compliant
            else f"Compliance check failed with {len(violations)} issues: " + "; ".join(violations)
        )

        return BrandComplianceResult(
            is_compliant=is_compliant,
            violations=violations,
            readability_score=ari_score,
            reading_grade_level=grade_level,
            detected_forbidden_terms=detected_terms,
            tone_analysis=tone_analysis,
            platform_standards=platform_standards,
            feedback=feedback,
        )
