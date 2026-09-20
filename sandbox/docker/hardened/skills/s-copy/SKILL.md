---
name: s-copy
description: Deterministic copy validator, prohibited-term screener, claim-reference checker, and deduplication utility for CREAT-COPY.
---

# S_COPY: Deterministic Creative Utilities

Authorized Specialist: `CREAT-COPY` (Creative Content Specialist; `W_CREAT` has zero sandbox authority)
Permitted Operations: `prohibited_term_check`, `validate_claim_refs`, `validate_platform_format`, `validate_aspect_ratio`, `validate_safe_zone_metadata`, `validate_schema`, `deduplicate_variants`, `hash_artifact`, `format_validation`
Core Tool: Deterministic Copy & Creative Utility

## Execution Contract
- Strictly deterministic: schema checks, claim refs, character limits, channel scope, prohibited terms, aspect ratios, safe-zone metadata, format validation, deduplication, citation validation, and artifact hashing.
- ZERO generative authority: does NOT fabricate claims, hooks, headlines, visual briefs, social posts, or schedules (all creative generation is restricted to Creative LLM specialists).
- Strictly isolated: No external network access permitted (`network_policy: disabled`).
