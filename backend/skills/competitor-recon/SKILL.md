---
name: competitor-recon
description: Gathers competitor positioning, SERP rank signals, and content pillar breakdowns. Activate during research strategy formulation or market intelligence analysis.
compatibility: Requires Python 3.12+ and rootless Podman sandbox.
allowed-tools: Bash(python3:scripts/parse_serp.py)
---

# Competitor Reconnaissance Skill

## Objective
Extract competitor positioning strategies, search engine ranking hooks, and market whitespace from SERP results and public competitor landing pages.

## Activation Criteria
Activate this skill whenever:
1. `ResearchStrategySubgraph` identifies competitor intelligence gaps.
2. A new marketing campaign is initialized with positioning objectives.
3. Market positioning refresh or counter-positioning analysis is initiated.

## Execution Protocol
1. **Gather Search Signals:** Obtain target keyword SERP HTML or search engine JSON payload.
2. **Execute Sandboxed Parser:** Run `scripts/parse_serp.py` inside rootless Podman sandbox (`sandbox_service.py`):
   ```bash
   podman run --rm --security-opt=no-new-privileges --cap-drop=ALL --memory=512m --network=none -v /tmp/sandboxes/job_xxx:/workspace:ro marketing-os-worker-sandbox python3 /workspace/scripts/parse_serp.py
   ```
3. **Extract Insights:**
   - Dominant messaging pillars among top 5 organic search results.
   - Identified content gaps where our product/service offers differentiated value.
   - High-converting headline angles and counter-narrative hooks.
4. **Handoff:** Return structured findings to `ResearchStrategyAgent` for synthesis into `CampaignBlueprint`.
