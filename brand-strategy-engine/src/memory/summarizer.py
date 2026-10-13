"""Recursive state compression engine for token budget enforcement."""

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.tools.dom_parser import DOMParser


class TokenBudget:
    """Stage-based token budget allocations across 16,384 context window."""

    SYSTEM_RESERVE: int = 2500
    STAGE_INPUT_SLICE: int = 6000
    ACTIVE_SCRATCHPAD: int = 5500
    GENERATION_HEADROOM: int = 2384
    TOTAL_WINDOW: int = 16384


class StateSummarizer:
    """Condenses verbose DOM nodes and ReAct traces when exceeding 5,000 tokens."""

    MAX_TOKEN_BUDGET: int = 5000

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
    def offload_screenshot_buffer(
        cls,
        buffer_data: str,
        storage_dir: Optional[str] = None,
    ) -> str:
        """
        Offloads large visual screenshot base64 strings to storage directory and
        returns a lightweight cryptographic URI hash (blob://<sha256>).
        """
        target_dir = Path(storage_dir or os.getenv("EVIDENCE_STORAGE_PATH", "/app/evidence_blobs"))
        sha256 = hashlib.sha256(buffer_data.encode("utf-8")).hexdigest()
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            blob_path = target_dir / f"{sha256}.blob"
            if not blob_path.exists():
                blob_path.write_text(buffer_data, encoding="utf-8")
        except Exception:
            # Local fallback or read-only container environment: return lightweight URI hash
            pass
        return f"blob://{sha256}"

    @classmethod
    def compress_scratchpad(
        cls,
        scratchpad: Dict[str, Any],
        max_budget: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Applies recursive hierarchical compression if scratchpad exceeds token budget."""
        budget = max_budget if max_budget is not None else cls.MAX_TOKEN_BUDGET
        raw_repr = str(scratchpad)
        token_count = cls.estimate_tokens(raw_repr)

        if token_count <= budget:
            return scratchpad

        compressed: Dict[str, Any] = {}
        for key, value in scratchpad.items():
            # Check for large visual screenshot buffers
            if isinstance(value, str) and (
                key in ("screenshot", "image_base64", "base64_image", "screenshot_buffer")
                or value.startswith("data:image/")
                or len(value) > 2000
            ):
                if key in ("screenshot", "image_base64", "base64_image", "screenshot_buffer") or value.startswith("data:image/"):
                    compressed[key] = cls.offload_screenshot_buffer(value)
                elif "<html" in value.lower() or "<body" in value.lower():
                    compressed[key] = cls.condense_html(value)
                else:
                    compressed[key] = value[:800] + "... [truncated for context budget]"
            elif isinstance(value, str) and ("<html" in value.lower() or "<body" in value.lower()):
                compressed[key] = cls.condense_html(value)
            elif isinstance(value, list) and value and isinstance(value[0], dict) and "action" in value[0]:
                compressed[key] = cls.condense_react_trace(value)
            elif isinstance(value, dict):
                compressed[key] = cls.compress_scratchpad(value, max_budget=budget // 2)
            else:
                compressed[key] = value

        return compressed

