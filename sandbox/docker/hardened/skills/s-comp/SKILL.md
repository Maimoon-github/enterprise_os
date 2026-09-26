---
name: s-comp
description: Governed competitor price, ad library, and DOM extraction micro-tool for W_COMP.
---

# S_COMP: Price & Ad Scraper

Authorized Worker: `W_COMP` (Competitor Intel)
Permitted Operations: `gather_prices`, `parse_dom`, `track_ads`
Core Tool: Browser / DOM extraction tool
Network Policy: `controlled` (Strictly bounded by time-limited `SandboxEgressGrant` through Tinyproxy egress sidecar)

## Execution Contract
- Operates under strict egress allowlisting; private/metadata IPs and unauthorized domains are rejected fail-closed.
- Extracts competitor pricing trajectories, active ad counts, and DOM hooks.
- Emits structured competitor market signals without leaking unredacted traces.
