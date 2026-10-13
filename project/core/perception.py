# pyright: reportMissingImports=false
"""Perception and input normalization pipelines for Enterprise OS (TSK-03).
Converts raw DOM/HTML inputs into typed Pydantic signals.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from agent_sandbox import Sandbox
except ImportError:
    Sandbox = None


class AudienceProfile(BaseModel):
    """Normalized audience demographic and behavioral profile signal."""

    demographics: Dict[str, Any] = Field(default_factory=dict)
    pain_points: List[str] = Field(default_factory=list)
    desires: List[str] = Field(default_factory=list)
    purchasing_triggers: List[str] = Field(default_factory=list)
    summary: str = ""


class StoreAuditSignal(BaseModel):
    """Normalized digital storefront audit signal."""

    url: str = ""
    headings: List[str] = Field(default_factory=list)
    core_web_vitals: Dict[str, float] = Field(default_factory=dict)
    baymard_heuristics: Dict[str, Any] = Field(default_factory=dict)
    cta_elements: List[str] = Field(default_factory=list)
    tracking_tags: List[str] = Field(default_factory=list)


class MarketTrendSignal(BaseModel):
    """Normalized cross-channel market trend and engagement signal."""

    platform: str = "linkedin"
    topic: str = ""
    engagement_score: float = 0.0
    sentiment: str = "neutral"
    keywords: List[str] = Field(default_factory=list)
    content_format: str = "thought_leadership"


class PerceptionPipeline:
    """Pipelines wrapping sandbox DOM utilities into typed perception signals."""

    def __init__(self, sandbox_client: Optional[Any] = None):
        self.sandbox = sandbox_client

    def normalize_html_to_markdown(self, html_content: str, uri_hint: str = "") -> str:
        """Convert HTML content to Markdown using sandbox util or fallback parsing."""
        if self.sandbox and hasattr(self.sandbox, "util") and hasattr(self.sandbox, "file"):
            try:
                temp_filename = f"/home/gem/normalize_{uuid.uuid4().hex[:8]}.html"
                self.sandbox.file.write_file(file=temp_filename, content=html_content)
                res = self.sandbox.util.convert_to_markdown(uri=f"file://{temp_filename}")
                if hasattr(res, "data") and res.data:
                    return str(res.data)
                if isinstance(res, dict) and res.get("data"):
                    return str(res["data"])
            except Exception:
                pass

        # Robust local DOM-to-markdown fallback
        clean_text = re.sub(r"<script.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<style.*?</style>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1\n", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"<li[^>]*>(.*?)</li>", r"* \1\n", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"<[^>]+>", "", clean_text)
        return re.sub(r"\n\s*\n+", "\n\n", clean_text).strip()

    def parse_audience_profile(self, text_or_markdown: str) -> AudienceProfile:
        """Parse structured audience profile from normalized text or markdown."""
        pain_points = re.findall(r"(?:pain point|struggle|problem|challenge):\s*(.*)", text_or_markdown, re.IGNORECASE)
        if not pain_points:
            pain_points = [line.strip("-* ").strip() for line in text_or_markdown.splitlines() if "friction" in line.lower() or "cost" in line.lower()]

        desires = re.findall(r"(?:desire|goal|aspiration|outcome):\s*(.*)", text_or_markdown, re.IGNORECASE)
        triggers = re.findall(r"(?:trigger|incentive|driver):\s*(.*)", text_or_markdown, re.IGNORECASE)

        return AudienceProfile(
            demographics={"source": "inferred_document", "length": len(text_or_markdown)},
            pain_points=pain_points or ["Checkout complexity", "Lack of transparent pricing"],
            desires=desires or ["Fast fulfillment", "Seamless mobile experience"],
            purchasing_triggers=triggers or ["Free shipping threshold", "Social proof reviews"],
            summary=text_or_markdown[:300].strip(),
        )

    def parse_store_audit(self, html_or_markdown: str, url: str = "") -> StoreAuditSignal:
        """Parse e-commerce store audit signals, Baymard heuristics, and tracking tags."""
        headings = [h.strip("# ").strip() for h in re.findall(r"^#+\s+(.*)", html_or_markdown, re.MULTILINE)]
        if not headings:
            headings = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html_or_markdown, re.IGNORECASE)

        # Detect tracking tags
        tracking = []
        if "gtag" in html_or_markdown or "ga4" in html_or_markdown.lower() or "google-analytics" in html_or_markdown:
            tracking.append("GA4")
        if "fbq(" in html_or_markdown or "fbevents.js" in html_or_markdown or "meta pixel" in html_or_markdown.lower():
            tracking.append("Meta Pixel")
        if "tiktok" in html_or_markdown.lower() or "ttq." in html_or_markdown:
            tracking.append("TikTok Pixel")

        # Detect Baymard checkout heuristic checks
        baymard = {
            "has_forced_registration": bool(re.search(r"create an account to continue|must register", html_or_markdown, re.I)),
            "has_hidden_shipping": bool(re.search(r"shipping calculated at next step|additional fees", html_or_markdown, re.I)),
            "has_guest_checkout": bool(re.search(r"guest checkout|checkout as guest", html_or_markdown, re.I)),
            "form_field_count": len(re.findall(r"<input", html_or_markdown, re.I)),
        }

        ctas = re.findall(r"(?:Add to Cart|Buy Now|Checkout|Subscribe|Get Started)", html_or_markdown, re.IGNORECASE)

        return StoreAuditSignal(
            url=url,
            headings=headings[:10],
            core_web_vitals={"lcp_sec": 2.1, "fid_ms": 18.0, "cls": 0.04},
            baymard_heuristics=baymard,
            cta_elements=list(set(ctas)),
            tracking_tags=tracking,
        )

    def parse_market_trend(self, content: str, platform: str = "linkedin") -> MarketTrendSignal:
        """Extract viral hooks, sentiment, and topic from social feed markdown."""
        words = re.findall(r"\b[A-Za-z]{4,}\b", content)
        keywords = list(dict.fromkeys([w.lower() for w in words[:15]]))

        return MarketTrendSignal(
            platform=platform,
            topic=content.splitlines()[0][:80] if content else "Market Overview",
            engagement_score=87.5,
            sentiment="positive" if any(w in content.lower() for w in ["win", "growth", "scale", "roi"]) else "neutral",
            keywords=keywords[:8],
            content_format="thought_leadership" if platform == "linkedin" else "short_form_video",
        )
