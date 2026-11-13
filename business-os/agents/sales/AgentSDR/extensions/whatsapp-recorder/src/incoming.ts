/**
 * Pure helpers for a calling station's incoming calls: the service worker's
 * list of calls ringing on the number, kept until the call worker takes them
 * (agentsdrStation.takeIncomingCalls) and a little longer, so answerCall can
 * still find the tab a taken call rang in.
 *
 * Dependency-free (only types and a constant), so the service worker and
 * wa-hook can bundle it, and bun:test can run it.
 */

import { INCOMING_CALL_MAX_AGE_MS, type StationIncomingCall } from "../../../src/lib/calls/stationContract";

/** A ring as the service worker keeps it: the tab it rang in, and whether the call worker took it. */
export type IncomingEntry = { call: StationIncomingCall; tabId: number | null; taken: boolean };

/** Rings older than this are forgotten: WhatsApp gives up on a call after about 45 s. */
export const INCOMING_KEEP_MS = 60_000;

/** A ring's fields checked, or null when it is not one. */
export function asIncomingCall(value: unknown): StationIncomingCall | null {
  if (!value || typeof value !== "object") return null;
  const v = value as Record<string, unknown>;
  if (typeof v.waCallId !== "string" || !v.waCallId) return null;
  if (typeof v.at !== "number" || !Number.isFinite(v.at)) return null;
  return {
    waCallId: v.waCallId,
    phone: typeof v.phone === "string" && /^\+\d{6,15}$/.test(v.phone) ? v.phone : null,
    callerName: typeof v.callerName === "string" && v.callerName.trim() ? v.callerName.trim() : null,
    isVideo: v.isVideo === true,
    isGroup: v.isGroup === true,
    at: v.at,
  };
}

/** Adds a ring once (by waCallId); a repeat only fills in a number or name the first report lacked. Old rings are dropped. */
export function addIncoming(list: IncomingEntry[], call: StationIncomingCall, tabId: number | null, now: number): { list: IncomingEntry[]; added: boolean } {
  const kept = list.filter((entry) => now - entry.call.at < INCOMING_KEEP_MS);
  const existing = kept.find((entry) => entry.call.waCallId === call.waCallId);
  if (existing) {
    existing.call = { ...existing.call, phone: existing.call.phone ?? call.phone, callerName: existing.call.callerName ?? call.callerName };
    if (existing.tabId === null) existing.tabId = tabId;
    return { list: kept, added: false };
  }
  if (now - call.at >= INCOMING_KEEP_MS) return { list: kept, added: false };
  return { list: [...kept, { call, tabId, taken: false }], added: true };
}

/** The ring stopped (answered elsewhere, hung up, or missed): it is not offered again. */
export function endIncoming(list: IncomingEntry[], waCallId: string): IncomingEntry[] {
  return list.filter((entry) => entry.call.waCallId !== waCallId);
}

/**
 * The rings not taken yet and young enough to answer, oldest first; they are
 * marked taken (kept for answerCall to find their tab) and stale ones dropped.
 */
export function takeIncoming(list: IncomingEntry[], now: number): { taken: StationIncomingCall[]; list: IncomingEntry[] } {
  const kept = list.filter((entry) => now - entry.call.at < INCOMING_KEEP_MS);
  const taken: StationIncomingCall[] = [];
  for (const entry of kept) {
    if (entry.taken || now - entry.call.at >= INCOMING_CALL_MAX_AGE_MS) continue;
    entry.taken = true;
    taken.push(entry.call);
  }
  taken.sort((a, b) => a.at - b.at);
  return { taken, list: kept };
}

/** WhatsApp's answer button on an incoming call, by its label or text — never Decline. */
export function isAcceptLabel(text: string | null | undefined): boolean {
  const value = (text ?? "").trim();
  return /^(accept|answer)( (voice |video |audio )?call)?$/i.test(value) && !/decline|reject|ignore/i.test(value);
}

/** For logs: a button's label with any digits hidden (a caller's number must not reach the log). */
export function maskDigits(text: string): string {
  return text.replace(/\d/g, "#");
}

/**
 * A phone number written on the incoming-call screen (an unsaved caller is
 * shown by number, "+91 96000 00001"), E.164, or null. Needs a leading "+"
 * so that a time or a count is never taken for one.
 */
export function phoneFromScreenText(text: string | null | undefined): string | null {
  const match = /\+\d[\d\s().-]{6,18}\d/.exec(text ?? "");
  if (!match) return null;
  const digits = match[0].replace(/\D/g, "");
  return digits.length >= 8 && digits.length <= 15 ? `+${digits}` : null;
}
