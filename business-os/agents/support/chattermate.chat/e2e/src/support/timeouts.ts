/**
 * How long a test waits for an AI answer: a cold embedding model plus a couple of
 * model calls. Longer than AGENT_RUN_TIMEOUT in .env.e2e, so a run the backend
 * gives up on surfaces as its fallback message rather than as a test timeout.
 */
export const AI_REPLY = { timeout: 30_000 } as const

/** How long a test waits for the knowledge worker to index a small source. */
export const KNOWLEDGE_INDEXED = { timeout: 60_000 } as const
