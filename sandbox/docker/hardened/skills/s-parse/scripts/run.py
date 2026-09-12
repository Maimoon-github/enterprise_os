#!/usr/bin/env python3
"""S_PARSE Sentiment & Review NLP Classifier Execution Script."""
import json
import re
import sys

def run_s_parse(payload: dict) -> dict:
    task_id = payload.get("task_id", "unknown")
    text = payload.get("feedback_text", payload.get("query", "Love the product quality but shipping took 10 days and support was slow."))

    positive_words = {"love", "great", "excellent", "fast", "effective", "good", "best", "satisfied"}
    negative_words = {"slow", "expensive", "shipping", "broke", "delayed", "poor", "difficult", "bad"}

    tokens = set(re.findall(r"\b\w+\b", text.lower()))
    pos_count = len(tokens & positive_words)
    neg_count = len(tokens & negative_words)

    total = pos_count + neg_count or 1
    polarity = (pos_count - neg_count) / total

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

if __name__ == "__main__":
    raw_input = sys.stdin.read()
    data = json.loads(raw_input) if raw_input.strip() else {}
    result = run_s_parse(data)
    sys.stdout.write(json.dumps(result))
