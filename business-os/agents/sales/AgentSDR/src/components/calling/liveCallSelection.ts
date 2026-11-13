import type { CallStatus } from "@/lib/calls/contract";

export type LiveCallCandidate = { id: string; status: CallStatus; createdAt: string };

/** A call fresher than this still counts as "just placed" even once it's terminal. */
const RECENT_WINDOW_MS = 10 * 60 * 1000;

/**
 * Which call id, if any, a ContactPanel's LiveCallStrip should watch.
 *
 * Prefers the contact's own latest call once it's in flight (pending or
 * in_progress) or was just placed (created in the last 10 minutes) — the
 * common case, once the panel's own poll has loaded the contact's calls.
 *
 * Otherwise falls back to whatever call most recently pushed a live update
 * in this tab (`latestLiveCallId`), but only when that update can plausibly
 * belong to this contact: either its id is already among the contact's
 * loaded calls, or the contact has no calls loaded yet at all — the panel
 * may have opened before its first poll resolved, so there's nothing here
 * yet to rule the update out.
 */
export function selectLiveCallId(params: {
  latestCall: LiveCallCandidate | null;
  callIds: readonly string[];
  latestLiveCallId: string | null;
  now?: number;
}): string | null {
  const { latestCall, callIds, latestLiveCallId, now = Date.now() } = params;

  if (latestCall) {
    const inFlight = latestCall.status === "pending" || latestCall.status === "in_progress";
    const justPlaced = now - new Date(latestCall.createdAt).getTime() < RECENT_WINDOW_MS;
    if (inFlight || justPlaced) return latestCall.id;
  }

  if (latestLiveCallId && (callIds.length === 0 || callIds.includes(latestLiveCallId))) {
    return latestLiveCallId;
  }

  return null;
}
