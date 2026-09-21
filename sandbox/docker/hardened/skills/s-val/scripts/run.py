#!/usr/bin/env python3
"""S_VAL Compliance Linter and Specialist Execution Script."""
import json
import re
import sys

def run_s_val(payload: dict) -> dict:
    task_id = payload.get("task_id", "unknown")
    tenant_id = payload.get("tenant_id", "default")
    operation = payload.get("operation", "default")
    specialist_role = payload.get("specialist_role", payload.get("specialist_id", "s_val"))

    # 1. Prohibited claim check patterns
    prohibited_claim_patterns = [
        r"\bcures?\b",
        r"\b100% guaranteed\b",
        r"\bprevents? all\b",
        r"\bpermanent elimination\b",
    ]

    violations = []

    # Inspect claims in payload or context_slice
    claims_raw = (
        payload.get("claims")
        or payload.get("claim")
        or payload.get("statement")
        or (payload.get("context_slice", {}).get("claims") if isinstance(payload.get("context_slice"), dict) else None)
        or (payload.get("context_slice", {}).get("claim") if isinstance(payload.get("context_slice"), dict) else None)
    )
    claims_to_check = []
    if isinstance(claims_raw, list):
        for c in claims_raw:
            if isinstance(c, dict):
                claims_to_check.append(c.get("text", c.get("claim", "")))
            else:
                claims_to_check.append(str(c))
    elif isinstance(claims_raw, str) and claims_raw:
        try:
            parsed = json.loads(claims_raw)
            if isinstance(parsed, list):
                claims_to_check = [item.get("text", str(item)) if isinstance(item, dict) else str(item) for item in parsed]
            else:
                claims_to_check = [claims_raw]
        except Exception:
            claims_to_check = [claims_raw]

    required_disclaimer = payload.get("required_disclaimer", "*Results may vary based on usage.")

    for claim_text in claims_to_check:
        for pattern in prohibited_claim_patterns:
            if re.search(pattern, claim_text, re.IGNORECASE):
                violations.append(f"Prohibited absolute claim pattern detected in '{claim_text}': {pattern}")
        disclaimer_present = required_disclaimer.lower() in claim_text.lower() or "*results" in claim_text.lower()
        if not disclaimer_present and "%" in claim_text:
            violations.append(f"Quantitative claim '{claim_text}' requires statutory disclaimer footnote.")

    # 2. Vision capability authorization check for imagery inspection
    if operation == "inspect_claim_imagery":
        vision_granted = payload.get("vision_granted", False)
        if not vision_granted:
            violations.append("Vision capability was requested for inspect_claim_imagery but is not granted.")

    compliance_score = max(0.0, 1.0 - (len(violations) * 0.4))
    is_compliant = len(violations) == 0

    primary_claim = claims_to_check[0] if claims_to_check else ""

    # 3. Role-scoped structured findings
    typed_findings = {
        "operation": operation,
        "specialist_role": specialist_role,
        "is_compliant": is_compliant,
        "violations": violations,
        "compliance_score": round(compliance_score, 2),
    }

    if operation == "validate_formulation":
        typed_findings["formulation_status"] = "VALIDATED" if is_compliant else "FLAGGED"
    elif operation == "assess_safety":
        typed_findings["safety_status"] = "NO_CONCERN_IDENTIFIED_IN_SCOPE" if is_compliant else "CONCERN_IDENTIFIED"
    elif operation == "check_regulatory_rules":
        typed_findings["regulatory_status"] = "MEETS_CHECKED_REQUIREMENT" if is_compliant else "DOES_NOT_MEET_CHECKED_REQUIREMENT"
    elif operation == "appraise_evidence":
        typed_findings["evidence_quality"] = "HIGH" if is_compliant else "LOW"
    elif operation in ("research_literature", "fetch_official_rules", "acquire_source"):
        typed_findings["sources_acquired"] = len(payload.get("input_manifest", []))

    return {
        "status": "success" if is_compliant else "compliance_warning",
        "task_id": task_id,
        "tenant_id": tenant_id,
        "operation": operation,
        "specialist_role": str(specialist_role),
        "claim": primary_claim,
        "is_compliant": str(is_compliant),
        "compliance_score": f"{compliance_score:.2f}",
        "violations": json.dumps(violations),
        "typed_findings": json.dumps(typed_findings),
        "verified_dossier": f"Claim: {primary_claim} | Compliance Score: {compliance_score:.2f} | Status: {'APPROVED' if is_compliant else 'FLAGGED'}",
    }

if __name__ == "__main__":
    raw_input = sys.stdin.read()
    data = json.loads(raw_input) if raw_input.strip() else {}
    result = run_s_val(data)
    sys.stdout.write(json.dumps(result))

