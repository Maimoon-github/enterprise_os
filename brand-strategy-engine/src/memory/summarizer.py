"""Recursive state compression engine for token budget enforcement."""

from typing import Any, Dict, List
from src.tools.dom_parser import DOMParser


class StateSummarizer:
    """Condenses verbose DOM nodes and ReAct traces when exceeding 5,000 tokens."""

    MAX_TOKEN_BUDGET = 5000

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Approximates token count based on character count heuristic (4 chars per token)."""
        return max(1, len(text) // 4)

    @classmethod
    def condense_html(cls, html: str) -> Dict[str, Any]:
        """Prunes raw HTML to accessibility tree outline and heading hierarchy."""
        metadata = DOMParser.extract_metadata(html)
        headings = DOMParser.extract_heading_hierarchy(html)
        acc_tree = DOMParser.build_accessibility_tree(html)

        return {
            "title": metadata.get("title", ""),
            "meta_description": metadata.get("meta_tags", {}).get("description", ""),
            "primary_headings": headings[:15],
            "landmarks": acc_tree.get("children", [])[:10],
        }

    @classmethod
    def condense_react_trace(cls, traces: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Converts detailed ReAct steps into structured observation digests."""
        condensed = []
        for step in traces:
            condensed.append({
                "step": str(step.get("step", "")),
                "action": str(step.get("action", "")),
                "observation_digest": str(step.get("observation", ""))[:200],
            })
        return condensed

    @classmethod
    def compress_scratchpad(cls, scratchpad: Dict[str, Any]) -> Dict[str, Any]:
        """Applies recursive compression if scratchpad exceeds MAX_TOKEN_BUDGET."""
        raw_repr = str(scratchpad)
        token_count = cls.estimate_tokens(raw_repr)

        if token_count <= cls.MAX_TOKEN_BUDGET:
            return scratchpad

        compressed: Dict[str, Any] = {}
        for key, value in scratchpad.items():
            if isinstance(value, str) and ("<html" in value.lower() or "<body" in value.lower()):
                compressed[key] = cls.condense_html(value)
            elif isinstance(value, list) and value and isinstance(value[0], dict) and "action" in value[0]:
                compressed[key] = cls.condense_react_trace(value)
            elif isinstance(value, str) and len(value) > 1000:
                compressed[key] = value[:800] + "... [truncated for context budget]"
            else:
                compressed[key] = value

        return compressed
