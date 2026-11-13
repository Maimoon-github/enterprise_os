/**
 * When a transcription still "pending" is stuck rather than slow. The server
 * transcribes after the upload without anyone waiting on it; if it restarts
 * mid-way the call stays "pending" for good. It lets a retry take such a call
 * over once it has been pending for 10 minutes (claimForRetry in
 * transcription.ts), so the Retry button appears just after that. Pure;
 * client-safe.
 */

import type { CallSummary } from "./contract";

export const TRANSCRIPT_STUCK_AFTER_MS = 11 * 60 * 1000;

export function transcriptLooksStuck(
  call: Pick<CallSummary, "transcriptStatus" | "endedAt" | "createdAt">,
  now = Date.now(),
): boolean {
  if (call.transcriptStatus !== "pending") return false;
  const since = Date.parse(call.endedAt ?? call.createdAt);
  return Number.isFinite(since) && now - since > TRANSCRIPT_STUCK_AFTER_MS;
}
