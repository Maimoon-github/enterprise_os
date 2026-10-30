---
name: brand-voice-audit
description: Audits campaign draft copy against core brand tone, vocabulary prohibitions, and style guidelines.
compatibility: Requires Python 3.12+ and BrandRAG MCP server.
allowed-tools: mcp_brand_rag:search_brand_knowledge Bash(python3:scripts/check_tone.py)
---

# Brand Voice Audit Skill

## Objective
Evaluate marketing copy against tone parameters and vocabulary rules.

## Protocol
1. Retrieve brand voice guidelines from `BrandRAG`.
2. Execute `scripts/check_tone.py` with proposed copy as stdin.
3. If tone score < 0.85, return structured critique to creative agent.
