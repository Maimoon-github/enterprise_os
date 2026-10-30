---
name: brand-voice-audit
description: Audits campaign draft copy against core brand tone, vocabulary prohibitions, and style guidelines. Activate during campaign creative review or when brand compliance scoring is requested.
compatibility: Requires Python 3.12+ and BrandRAG MCP server.
allowed-tools: mcp_brand_rag:search_brand_knowledge Bash(python3:scripts/check_tone.py)
---

# Brand Voice Audit Skill

## Objective
Evaluate marketing copy against tone parameters, prohibited vocabulary, and readability rules to guarantee consistency with the master brand identity.

## Activation Criteria
Activate this skill whenever:
1. `CampaignCreativeSubgraph` produces draft platform assets.
2. The orchestrator invokes the human approval preparation step (`prepare_publish_payload_node`).
3. An operator or brand manager requests an explicit brand voice compliance audit.

## Operational Workflow
1. **Retrieve Guidelines:** Fetch brand tone parameters via `mcp_brand_rag:search_brand_knowledge`.
2. **Execute Deterministic Audit:** Run `scripts/check_tone.py` with proposed copy via stdin or sandbox runner.
3. **Analyze Metrics:**
   - **Buzzword Violations:** Zero-tolerance check on forbidden corporate jargon ("game-changer", "synergy", "paradigm shift", "disruptive").
   - **Readability:** Average sentence length must remain $\le 30$ words.
   - **Passing Threshold:** Aggregate tone score must exceed $0.85$.
4. **Reflexion Loop:** If tone score $< 0.85$, generate structured critique feedback detailing exact offending phrases and suggested positioning replacements.
