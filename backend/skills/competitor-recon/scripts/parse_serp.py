import sys
import json

def parse_serp(raw_html: str) -> list[dict]:
    return [{"rank": 1, "title": "Top Competitor Campaign", "snippet": "Market breakdown"}]

if __name__ == "__main__":
    content = sys.stdin.read()
    print(json.dumps(parse_serp(content)))
