---
name: multi-platform-copy
description: Adapts master brand messaging across 8 social platforms conforming to strict character limits and native hook structures. Activate during creative copywriting and cross-platform adaptation workflows.
compatibility: Universal LLM text generation runtime.
allowed-tools: none
---

# Multi-Platform Copy Skill

## Objective
Transform single positioning briefs and narrative hooks into high-performing, platform-native copy variants across all 8 supported social channels.

## Activation Criteria
Activate this skill whenever:
1. `CampaignCreativeSubgraph` is drafting or revising copy for target platforms.
2. An operator creates new campaign platform assets.
3. Repurposing long-form content into cross-channel snippets.

## Channel Specific Rules
Always consult `references/PLATFORM_LIMITS.md` before finalizing platform text:
- **LinkedIn:** Hard limit 3,000 chars. Ensure the hook captures attention within the first 210 characters (before "...see more"). Use 3–5 industry hashtags.
- **YouTube:** Title $\le 100$ characters. Description $\le 5,000$ characters with timestamped chapters and link in first 150 characters. Shorts duration $\le 60\text{s}$.
- **Instagram:** Hard limit 2,200 chars. Place key takeaway and call-to-action in the first 125 chars. Maximum 30 hashtags.
- **Threads:** Punchy text $\le 500$ characters. Conversational opening hook.
- **Facebook:** Recommended 80 characters for feed engagement (hard ceiling 63,206).
- **X (Twitter):** Hard limit 280 characters. Single focused hook, maximum 2 relevant hashtags, crisp value proposition.
- **Pinterest:** Pin title $\le 100$ characters, description $\le 500$ characters emphasizing visual problem solving.
- **Google Business Profile:** Post length $\le 1,500$ characters (recommended 150–300 chars) with a direct action CTA ("Learn more", "Sign up").
