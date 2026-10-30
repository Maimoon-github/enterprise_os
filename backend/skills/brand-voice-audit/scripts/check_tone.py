import sys
import json

def audit_tone(text: str) -> dict:
    # Rule-based tone check for prohibited buzzwords
    prohibited = ["game-changer", "synergy", "paradigm shift", "disruptive"]
    violations = [w for w in prohibited if w in text.lower()]
    score = 1.0 - (0.25 * len(violations))
    return {
        "score": max(score, 0.0),
        "violations": violations,
        "passed": len(violations) == 0
    }

if __name__ == "__main__":
    content = sys.stdin.read()
    print(json.dumps(audit_tone(content)))
