/**
 * How the calls UI follows a call that is still settling — in flight, or
 * transcribing: poll this often, and give up after this long (a stuck
 * transcript gets its own Retry, see src/lib/calls/transcriptState.ts).
 */
export const CALL_POLL_INTERVAL_MS = 5_000;
export const CALL_POLL_TIMEOUT_MS = 15 * 60 * 1000;
