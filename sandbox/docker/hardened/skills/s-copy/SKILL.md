---
name: s-copy
description: Copy variant generator, hook critic, and brand voice screening micro-tool for W_CREAT.
---

# S_COPY: Copy Drafter & Hook Critic

Authorized Worker: `W_CREAT` (Creative Content)
Permitted Operations: `generate_variants`, `score_hooks`, `format_validation`
Core Tool: Variant generator / hook critic

## Execution Contract
- Accepts brand voice guidelines, campaign objective, and prohibited terms.
- Generates diversified hook candidates, screens against brand guardrails, and ranks by engagement heuristics.
- Strictly isolated: No external network access permitted (`network_policy: disabled`).
