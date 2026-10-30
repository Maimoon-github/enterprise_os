#!/usr/bin/env python3
import json
import sys


def audit_tone(text: str) -> dict:
    if not text.strip():
        return {
            "score": 0.0,
            "passed": False,
            "violations": ["empty_content"],
            "word_count": 0,
            "prohibited_words_found": [],
            "recommendation": "Provide non-empty campaign copy text for tone evaluation.",
        }

    prohibited = [
        "game-changer",
        "synergy",
        "paradigm shift",
        "disruptive",
        "revolutionary",
        "world-class",
        "leverage synergies",
        "deep dive",
    ]
    text_lower = text.lower()
    violations = [w for w in prohibited if w in text_lower]

    words = text.split()
    word_count = len(words)
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    avg_sentence_len = (word_count / len(sentences)) if sentences else 0

    penalty = len(violations) * 0.25
    if avg_sentence_len > 35:
        penalty += 0.15

    score = max(round(1.0 - penalty, 2), 0.0)
    passed = score >= 0.75 and len(violations) == 0

    return {
        "score": score,
        "passed": passed,
        "violations": violations,
        "word_count": word_count,
        "sentence_count": len(sentences),
        "avg_sentence_length": round(avg_sentence_len, 1),
        "prohibited_words_found": violations,
        "recommendation": "Copy complies with brand guidelines."
        if passed
        else f"Remove buzzwords ({', '.join(violations)}) and keep sentences under 30 words.",
    }


if __name__ == "__main__":
    content = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(audit_tone(content), indent=2))
