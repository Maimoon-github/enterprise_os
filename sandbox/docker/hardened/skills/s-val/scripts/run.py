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

    # 3. Disclosure-safe search query check for discovery
    if operation in ("research_literature", "acquire_source"):
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        query = payload.get("query") or ctx.get("query")
        if query:
            for pattern in (r"\b(secret|confidential|proprietary|unreleased|internal_batch)\b",):
                if re.search(pattern, str(query), re.IGNORECASE):
                    violations.append(f"Disclosure-safety violation: Confidential pattern detected in search query '{query}': {pattern}")

    # 4. Formulation, Lab Audit, and Method Verification checks
    if operation in ("validate_formulation", "audit_lab_report", "verify_test_methods"):
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        if ctx.get("batch_mismatch"):
            violations.append("Batch mismatch: formulation/sample batch does not match target product specification.")
        if ctx.get("missing_density"):
            violations.append("Density missing: volume-to-mass concentration conversion attempted without density.")
        if ctx.get("unbridged_ingredient_claim"):
            violations.append("Unbridged ingredient evidence: cannot transfer ingredient evidence to finished product without an explicit comparability bridge.")
        if ctx.get("accreditation_out_of_scope"):
            violations.append("Accreditation scope violation: test method is outside verified laboratory accreditation scope.")
        if ctx.get("report_hash_missing") or ctx.get("report_hash_mismatch"):
            violations.append("Report integrity violation: report hash is missing or fails verification.")
        if ctx.get("unverified_visual_elements"):
            violations.append("Report authenticity unverified: visual signatures or logos present without verified credentials.")
        if ctx.get("method_unsupported"):
            violations.append("Unsupported test method: method is not recognized or lacks standard validation.")

    # 5. Appraisal & Safety checks
    if operation in ("appraise_evidence", "assess_study_design", "grade_certainty"):
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        if ctx.get("unresolved_conflicts_unflagged"):
            violations.append("Unresolved scientific conflicts detected but not flagged in conflict records.")
        if ctx.get("missing_evidence_treated_as_absence"):
            violations.append("Methodological violation: absence of evidence cannot be treated as evidence of absence.")
        if ctx.get("duplicate_cohort_inflation"):
            violations.append("Methodological violation: duplicate publications from same cohort cannot inflate consistency.")

    if operation in ("assess_safety", "evaluate_hazards", "screen_adverse_signals"):
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        if ctx.get("severe_adverse_signal"):
            violations.append("Severe adverse signal detected: immediate escalation and review hold required.")
        if ctx.get("vulnerable_population_unassessed"):
            violations.append("Safety coverage gap: vulnerable population exposure not assessed.")
        if ctx.get("unrestricted_safe_claim"):
            violations.append("Prohibited safety claim: unrestricted 'safe' declaration is prohibited.")

    if operation in ("extract_claims", "map_claims", "map_claim_evidence", "evaluate_claim_evidence_edges", "interpret_claims"):
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        if ctx.get("ingredient_without_bridge"):
            violations.append("Evidence bridging violation: finished-product claim relies on ingredient evidence without an applicable bridge.")
        if ctx.get("scope_mismatch_unqualified"):
            violations.append("Scope overreach violation: claim magnitude, duration, population, endpoint, or route exceeds evidence without qualification.")
        if ctx.get("unsupported_claim_unflagged"):
            violations.append("Unsupported claim violation: proposition lacks supporting evidence and was not flagged.")

    if operation in ("check_regulatory_rules", "apply_rules", "verify_statutory_requirements"):
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        if ctx.get("rule_unverified_or_superseded"):
            violations.append("Regulatory applicability violation: unverified, superseded, or non-commenced rule cannot yield compliance pass.")
        if ctx.get("guidance_promoted_to_statute"):
            violations.append("Legal force violation: non-binding guidance cannot be promoted to statutory mandate.")
        if ctx.get("unsupported_jurisdiction"):
            violations.append("Territory mismatch violation: rule jurisdiction does not match product target market.")
        if ctx.get("disease_claim_on_cosmetic"):
            violations.append("Statutory classification breach: therapeutic/medicinal claim prohibited on cosmetic product class.")

    compliance_score = max(0.0, 1.0 - (len(violations) * 0.4))
    is_compliant = len(violations) == 0

    primary_claim = claims_to_check[0] if claims_to_check else ""

    # 6. Role-scoped structured findings
    typed_findings = {
        "operation": operation,
        "specialist_role": specialist_role,
        "is_compliant": is_compliant,
        "violations": violations,
        "compliance_score": round(compliance_score, 2),
    }

    if operation == "validate_formulation":
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        typed_findings["formulation_status"] = "VALIDATED" if is_compliant else "FLAGGED"
        typed_findings["formulation_bridge"] = ctx.get("formulation_bridge", {})
        typed_findings["product_specification"] = ctx.get("product_specification", {})
        typed_findings["normalized_measurements"] = ctx.get("normalized_measurements", [])
    elif operation == "audit_lab_report":
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        typed_findings["audit_outcome"] = "VALIDATED" if is_compliant else "FLAGGED"
        typed_findings["lab_validation"] = ctx.get("lab_validation", {})
        typed_findings["conformity_assessment"] = ctx.get("conformity_assessment", "PASS" if is_compliant else "UNKNOWN")
    elif operation == "verify_test_methods":
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        typed_findings["method_status"] = "VERIFIED" if is_compliant else "UNVERIFIED"
        typed_findings["test_methods"] = ctx.get("test_methods", [])
    elif operation in ("appraise_evidence", "assess_study_design", "grade_certainty"):
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        typed_findings["evidence_quality"] = ctx.get("evidence_quality", "HIGH" if is_compliant else "LOW")
        typed_findings["consistency"] = ctx.get("consistency", "consistent")
        typed_findings["evidence_assessments"] = ctx.get("evidence_assessments", [])
        typed_findings["conflict_records"] = ctx.get("conflict_records", [])
        typed_findings["evidence_gaps"] = ctx.get("evidence_gaps", [])
    elif operation in ("assess_safety", "evaluate_hazards", "screen_adverse_signals"):
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        typed_findings["safety_status"] = ctx.get("safety_status", "NO_CONCERN_IDENTIFIED_IN_SCOPE" if is_compliant else "CONCERN_IDENTIFIED")
        typed_findings["safety_assessments"] = ctx.get("safety_assessments", [])
        typed_findings["adverse_signals"] = ctx.get("adverse_signals", [])
        typed_findings["qualified_reviewer_required"] = ctx.get("qualified_reviewer_required", True)
    elif operation in ("extract_claims", "map_claims", "map_claim_evidence", "evaluate_claim_evidence_edges", "interpret_claims"):
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        typed_findings["claim_status"] = ctx.get("claim_status", "SUPPORTED_IN_SCOPE" if is_compliant else "INSUFFICIENT")
        typed_findings["claims"] = ctx.get("claims", [])
        typed_findings["claim_evidence_edges"] = ctx.get("claim_evidence_edges", [])
        typed_findings["human_review_required"] = ctx.get("human_review_required", not is_compliant)
    elif operation in ("check_regulatory_rules", "apply_rules", "verify_statutory_requirements"):
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        typed_findings["regulatory_status"] = ctx.get("regulatory_status", "MEETS_CHECKED_REQUIREMENT" if is_compliant else "DOES_NOT_MEET_CHECKED_REQUIREMENT")
        typed_findings["rule_applications"] = ctx.get("rule_applications", [])
        typed_findings["regulatory_rules"] = ctx.get("regulatory_rules", [])
        typed_findings["escalation_required"] = ctx.get("escalation_required", not is_compliant)
    elif operation in ("research_literature", "fetch_official_rules", "acquire_source", "parse_metadata"):
        ctx = payload.get("context_slice", {}) if isinstance(payload.get("context_slice"), dict) else {}
        sources = ctx.get("sources", payload.get("sources", []))
        search_runs = ctx.get("search_runs", payload.get("search_runs", []))
        snapshots = ctx.get("snapshots", payload.get("snapshots", []))
        extracted_ev = ctx.get("extracted_evidence", payload.get("extracted_evidence", []))
        exclusions = ctx.get("exclusions", payload.get("exclusions", []))
        stopping_reason = ctx.get("stopping_reason", payload.get("stopping_reason", "saturation"))

        typed_findings["sources_acquired"] = len(sources) if sources else len(payload.get("input_manifest", []))
        typed_findings["sources"] = sources
        typed_findings["search_runs"] = search_runs
        typed_findings["snapshots"] = snapshots
        typed_findings["extracted_evidence"] = extracted_ev
        typed_findings["exclusions"] = exclusions
        typed_findings["stopping_reason"] = stopping_reason

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

