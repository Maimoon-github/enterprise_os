import type { CallStatus } from "@/lib/calls/contract";

/**
 * How a call's status reads in the calls lists. "Not connected" rather than
 * "rejected": the app cannot tell a declined call from one that never rang
 * (unreachable, cut, WhatsApp closed) — the call's error says which, when
 * known.
 */
export const CALL_STATUS_LABEL: Record<CallStatus, string> = {
  pending: "Calling…",
  in_progress: "On call",
  recorded: "Recorded",
  no_recording: "Not connected",
  failed: "Failed",
};

export const CALL_STATUS_TONE: Record<CallStatus, "neutral" | "success" | "info" | "danger" | "warning"> = {
  pending: "warning",
  in_progress: "info",
  recorded: "success",
  no_recording: "neutral",
  failed: "danger",
};
