"""Semantic accessibility tree and DOM metadata extractor."""

import json
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup


class DOMParser:
    """Parses raw HTML into structured semantic representations."""

    @staticmethod
    def extract_metadata(html: str) -> Dict[str, Any]:
        """Extracts title, meta tags, OpenGraph data, and JSON-LD schema blocks."""
        soup = BeautifulSoup(html, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        meta_tags: Dict[str, str] = {}
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property")
            content = meta.get("content")
            if name and content:
                meta_tags[str(name)] = str(content)

        # JSON-LD extraction
        json_ld_blocks: List[Dict[str, Any]] = []
        for script in soup.find_all("script", type="application/ld+json"):
            if script.string:
                try:
                    parsed = json.loads(script.string.strip())
                    json_ld_blocks.append(parsed)
                except json.JSONDecodeError:
                    continue

        # OpenGraph extraction
        opengraph: Dict[str, str] = {}
        for meta in soup.find_all("meta"):
            prop = meta.get("property") or meta.get("name")
            content = meta.get("content")
            if prop and content and str(prop).startswith("og:"):
                opengraph[str(prop)] = str(content)

        canonical_tag = soup.find("link", rel="canonical")
        canonical_href = ""
        if canonical_tag and hasattr(canonical_tag, "get"):
            canonical_href = str(canonical_tag.get("href") or "")

        return {
            "title": title,
            "meta_tags": meta_tags,
            "opengraph": opengraph,
            "json_ld": json_ld_blocks,
            "canonical": canonical_href,
        }

    @staticmethod
    def extract_heading_hierarchy(html: str) -> List[Dict[str, str]]:
        """Extracts ordered heading structures (h1-h6) to diagnose semantic hierarchy."""
        soup = BeautifulSoup(html, "html.parser")
        headings: List[Dict[str, str]] = []

        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            text = tag.get_text(strip=True)
            if text:
                headings.append({"level": tag.name, "text": text})

        return headings

    @staticmethod
    def build_accessibility_tree(html: str) -> Dict[str, Any]:
        """Builds a condensed, semantic DOM accessibility tree."""
        soup = BeautifulSoup(html, "html.parser")

        # Strip unhelpful non-content tags
        for element in soup(["script", "style", "noscript", "svg"]):
            element.decompose()

        def parse_node(node) -> Optional[Dict[str, Any]]:
            if getattr(node, "name", None) is None:
                text = str(node).strip()
                return {"type": "text", "value": text} if text else None

            tag_name = node.name.lower()
            role = node.get("role") or tag_name
            node_dict: Dict[str, Any] = {
                "tag": tag_name,
                "role": role,
            }

            if node.get("id"):
                node_dict["id"] = node["id"]
            if node.get("class"):
                node_dict["classes"] = " ".join(node["class"])
            if node.get("aria-label"):
                node_dict["aria_label"] = node["aria-label"]
            if tag_name == "a" and node.get("href"):
                node_dict["href"] = node["href"]
            if tag_name in ("button", "input") and node.get("value"):
                node_dict["value"] = node["value"]

            children = []
            for child in node.children:
                child_repr = parse_node(child)
                if child_repr:
                    children.append(child_repr)

            if children:
                node_dict["children"] = children
            else:
                direct_text = node.get_text(strip=True)
                if direct_text:
                    node_dict["text"] = direct_text[:150]

            return node_dict

        body = soup.find("body") or soup
        return parse_node(body) or {"tag": "body", "children": []}
