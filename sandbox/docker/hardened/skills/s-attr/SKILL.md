---
name: s-attr
description: Multi-touch attribution, creative decay, fatigue detection, and learning delta modeler micro-tool for W_LEARN.
---

# S_ATTR: Attribution Modeler

Authorized Specialists: `LEARN-TELEMETRY`, `LEARN-ATTRIBUTION`, `LEARN-INCREMENTALITY`, `LEARN-FATIGUE`, `LEARN-DECAY`, `LEARN-QA`
Coordinator Authority: `W_LEARN` coordinator has ZERO direct sandbox access.
Permitted Operations: `validate_telemetry`, `normalize_telemetry`, `summarize_quality`, `estimate_attribution`, `fit_mmm`, `calculate_roas`, `validate_experiment`, `estimate_lift`, `propose_calibration`, `analyze_wearout`, `analyze_saturation`, `estimate_adstock`, `estimate_half_life`, `diagnose_decay`, `validate_learning_bundle`, `reconcile_estimates`, `verify_provenance`, `calculate_attribution`, `score_decay`, `fatigue_scoring`
Core Tools: Attribution, MMM, decay kernels, ITT lift, and QA verification micro-tools

## Execution Contract
- Accepts bounded, immutable dataset references and scoped analytical parameters.
- Applies deterministic attribution, adstock, Hill response, decay, and causal lift modeling.
- Strictly isolated: No external network access permitted (`network_policy: disabled`).
- Provider credentials and enterprise datastores are strictly excluded from container execution.
