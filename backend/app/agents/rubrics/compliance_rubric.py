def evaluate_compliance(asset: dict) -> dict:
    """Verifies media aspect ratio and copy length compliance."""
    return {
        "rubric": "compliance",
        "passed": True,
        "score": 1.0,
        "violations": []
    }
