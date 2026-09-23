---
name: s-parse
description: Sentiment, review, and customer objection parser micro-tool for W_VOICE.
---

# S_PARSE: Sentiment & Review Parser

Authorized Worker / Specialists: `VOICE-DISCOVERY`, `VOICE-THEMES`, `VOICE-SENTIMENT`, `VOICE-NEEDS`, `VOICE-JOURNEY`, `VOICE-QA` (Zero-sandbox coordinator `W_VOICE` is prohibited)
Permitted Operations: `parse_sentiment`, `cluster_objections`, `extract_feedback`, `discover_feedback`, `extract_themes`, `extract_needs`, `map_journey`, `qa_audit`
Core Tool: NLP classifier / sentiment & objection parser

## Execution Contract
- Accepts user reviews, ticket transcripts, and feedback text.
- Performs polarity scoring and clusters customer friction into structured objection categories.
- Strictly isolated: No external network access permitted (`network_policy: disabled`).
