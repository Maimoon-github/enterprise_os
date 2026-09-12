#!/usr/bin/env python3
"""S_VAL Compliance Linter Execution Script."""
import json
import re
import sys

def run_s_val(payload: dict) -> dict:
    task_id = payload.get("task_id", "unknown")
    claim_text = payload.get("claim", payload.get("statement", "Clinically tested to improve performance by 40%."))
    required_disclaimer = payload.get("required_disclaimer", "*Results may vary based on usage.")

    prohibited_claim_patterns = [
        r"\bcures?\b",
        r"\b100% guaranteed\b",
        r"\bprevents? all\b",
        r"\bpermanent elimination\b",
    ]

    violations = []
    for pattern in prohibited_claim_patterns:
        if re.search(pattern, claim_text, re.IGNORECASE):
            violations.append(f"Prohibited absolute claim pattern detected: {pattern}")

    disclaimer_present = required_disclaimer.lower() in claim_text.lower() or "*results" in claim_text.lower()
    if not disclaimer_present and "%" in claim_text:
        violations.append("Quantitative claim requires statutory disclaimer footnote.")

    compliance_score = max(0.0, 1.0 - (len(violations) * 0.4))
    is_compliant = len(violations) == 0

    return {
        "status": "success" if is_compliant else "compliance_warning",
        "task_id": task_id,
        "claim": claim_text,
        "is_compliant": str(is_compliant),
        "compliance_score": f"{compliance_score:.2f}",
        "violations": json.dumps(violations),
        "verified_dossier": f"Claim: {claim_text} | Compliance Score: {compliance_score:.2f} | Status: {'APPROVED' if is_compliant else 'FLAGGED'}",
    }

if __name__ == "__main__":
    raw_input = sys.stdin.read()
    data = json.loads(raw_input) if raw_input.strip() else {}
    result = run_s_val(data)
    sys.stdout.write(json.dumps(result))
