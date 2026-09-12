---
name: s-attr
description: Multi-touch attribution, creative decay, fatigue detection, and learning delta modeler micro-tool for W_LEARN.
---

# S_ATTR: Attribution Modeler

Authorized Worker: `W_LEARN` (Learning Performance)
Permitted Operations: `calculate_attribution`, `score_decay`, `fatigue_scoring`
Core Tool: Attribution / decay modeler

## Execution Contract
- Accepts ROAS metrics and active lifecycle duration in days.
- Applies exponential decay half-life modeling: $\text{decay} = e^{-\lambda \cdot t}$.
- Detects creative fatigue thresholds and outputs structured learning recommendations.
- Strictly isolated: No external network access permitted (`network_policy: disabled`).
