/**
 * Where a call the rep talks on through a calling station stands, from the
 * rep's side — the pure half of remoteRepCall.ts, so it can be tested without
 * a browser. `stationPresent`: the station has joined the call's audio relay.
 */

import { TERMINAL_CALL_STATUSES, type CallDetail } from "@/lib/calls/contract";
import { formatCallDuration } from "./formatElapsed";

export type RemoteRepStage =
  | "mic"
  | "placing"
  | "waiting"
  | "opening"
  | "dialing"
  | "ringing"
  | "on-call"
  | "ended"
  | "error";

export type RemoteRepView = { stage: RemoteRepStage; answeredAt?: number; message?: string };

export function isRemoteRepOver(stage: RemoteRepStage): stage is "ended" | "error" {
  return stage === "ended" || stage === "error";
}

export function remoteRepView(
  call: Pick<CallDetail, "status" | "livePhase" | "error" | "durationMs">,
  stationPresent: boolean,
): RemoteRepView {
  const phase = call.livePhase ?? null;
  switch (phase?.kind) {
    case "error":
      return { stage: "error", message: phase.message };
    case "not-answered":
      return { stage: "ended", message: "Not answered" };
    case "not-on-whatsapp":
      return { stage: "ended", message: "This number isn't on WhatsApp" };
    case "processing":
    case "done":
      return { stage: "ended", message: ended(phase.durationMs) };
  }
  if (TERMINAL_CALL_STATUSES.includes(call.status)) {
    if (call.status === "failed") return { stage: "error", message: call.error || "The call failed" };
    if (call.status === "recorded") return { stage: "ended", message: ended(call.durationMs) };
    return { stage: "ended", message: call.error || "The call ended before it connected" };
  }
  switch (phase?.kind) {
    case "on-call":
      // The station's clock, not ours: never let the timer start in the future.
      return { stage: "on-call", answeredAt: Math.min(phase.answeredAt, Date.now()) };
    case "ringing":
      return { stage: "ringing" };
    case "calling":
    case "manual-dial":
    case "audio-blocked":
      return { stage: "dialing" };
  }
  // Queued or opening WhatsApp; once the station has joined the relay, it is about to dial.
  if (stationPresent) return { stage: "dialing" };
  return { stage: !phase || phase.kind === "queued" ? "waiting" : "opening" };
}

function ended(durationMs: number | null): string {
  const length = formatCallDuration(durationMs);
  return length ? `Call ended · ${length}` : "Call ended";
}

/** What the browser said when the microphone was refused, in words for the rep. */
export function microphoneErrorText(error: unknown): string {
  const name = error instanceof DOMException || error instanceof Error ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Microphone access is blocked — allow it for this site (the icon in the address bar), then try again.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") return "No microphone found — plug one in and try again.";
  if (name === "NotReadableError") return "The microphone is in use by another app — close it and try again.";
  return error instanceof Error && error.message ? `Couldn't use the microphone: ${error.message}` : "Couldn't use the microphone.";
}
