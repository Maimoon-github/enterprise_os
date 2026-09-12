---
name: s-parse
description: Sentiment, review, and customer objection parser micro-tool for W_VOICE.
---

# S_PARSE: Sentiment & Review Parser

Authorized Worker: `W_VOICE` (Customer Voice)
Permitted Operations: `parse_sentiment`, `cluster_objections`, `extract_feedback`
Core Tool: NLP classifier / sentiment & objection parser

## Execution Contract
- Accepts user reviews, ticket transcripts, and feedback text.
- Performs polarity scoring and clusters customer friction into structured objection categories.
- Strictly isolated: No external network access permitted (`network_policy: disabled`).
