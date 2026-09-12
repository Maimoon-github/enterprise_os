---
name: s-val
description: Claim, schema, evidence, and regulatory compliance validation micro-tool for W_PROD.
---

# S_VAL: Claim & Schema Validator

Authorized Worker: `W_PROD` (Product Evidence)
Permitted Operations: `validate_claim`, `lint_compliance`, `check_schema`
Core Tool: Compliance / schema linter

## Execution Contract
- Accepts marketing and clinical claims, schemas, and required statutory disclaimers.
- Detects prohibited absolute claims (e.g. "cures", "100% guaranteed", "prevents all").
- Enforces statutory disclaimer footnotes for quantitative claims.
- Strictly isolated: No external network access permitted (`network_policy: disabled`).
