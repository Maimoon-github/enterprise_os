# Agent instructions

## UI implementation and verification

- For UI change requests, implement the requested change first and hand off concise manual verification guidance.
- Do not run Playwright, browser automation, screenshots, or lengthy interactive verification unless the user explicitly requests it.
- Prefer lightweight static checks only when they are necessary for the change.
- If browser verification would materially reduce uncertainty, ask the user to verify the behavior or request permission before running it.
