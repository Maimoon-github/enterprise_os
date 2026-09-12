---
name: s-alloc
description: Media and budget allocation optimization modeler micro-tool for W_STRAT.
---

# S_ALLOC: Media & Budget Allocator

Authorized Worker: `W_STRAT` (Strategy)
Permitted Operations: `optimize_budget`, `simulate_scenarios`, `calculate_roas`
Core Tool: Optimization modeler / diminishing returns solver

## Execution Contract
- Accepts budget totals, channel allowlists, and prior ROAS weights.
- Calculates optimal risk-adjusted budget distribution and expected blended ROAS.
- Strictly isolated: No external network access permitted (`network_policy: disabled`).
