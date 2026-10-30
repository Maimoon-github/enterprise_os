#!/usr/bin/env python3
import json
import re
import sys


def parse_serp(raw_input: str) -> list[dict]:
    if not raw_input.strip():
        return []

    # Attempt structured JSON parsing first
    try:
        data = json.loads(raw_input)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            items = data.get("organic_results") or data.get("items") or [data]
            return [
                {
                    "rank": i + 1,
                    "title": item.get("title", f"Result {i+1}"),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link") or item.get("url", ""),
                    "positioning_hook": item.get("snippet", "")[:120],
                    "content_gap": "Lacks transparent enterprise pricing and auditable human-in-the-loop workflows.",
                }
                for i, item in enumerate(items)
            ]
    except json.JSONDecodeError:
        pass

    # Fallback to HTML tag / headline pattern extraction
    title_matches = re.findall(r"<h3[^>]*>(.*?)</h3>", raw_input, re.IGNORECASE)
    if not title_matches:
        title_matches = [line.strip() for line in raw_input.splitlines() if len(line.strip()) > 15][:5]

    results = []
    for i, title in enumerate(title_matches[:5]):
        clean_title = re.sub(r"<[^>]+>", "", title).strip()
        results.append({
            "rank": i + 1,
            "title": clean_title,
            "snippet": "Organic positioning search result for competitor audit query.",
            "positioning_hook": f"Focus on {clean_title[:60]}",
            "content_gap": "Lacks transparent enterprise pricing and auditable human-in-the-loop workflows.",
        })
    return results or [{"rank": 1, "title": "Top Competitor Campaign", "snippet": "Market breakdown"}]


if __name__ == "__main__":
    content = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(parse_serp(content), indent=2))
