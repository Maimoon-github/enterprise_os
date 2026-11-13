/**
 * The pure half of AgentSDR's own WhatsApp messaging through calling stations
 * (stationMessaging.ts, messages.ts's ingestStationMessages): ids, chat keys,
 * the worker's reports, and the message-job state rules. No database here, so
 * it is unit-tested on its own.
 *
 * Ids. A station's whatsapp_accounts row is "station:<station id>" in
 * unipile_account_id. Its chats are keyed (whatsapp_chats.unipile_chat_id) by
 * the lead's "<digits>@s.whatsapp.net" — the same form Unipile's provider ids
 * take — or, when WhatsApp names the chat only by its "@lid" id and the
 * number cannot be resolved, by that id. A message is keyed
 * (whatsapp_messages.unipile_message_id, unique across every account) by
 * "station:<station id>:<WhatsApp key id>": the key id alone is the sender's,
 * so two stations in one conversation would otherwise collide.
 */

import {
  MAX_INBOUND_BATCH,
  type StationInboundMessage,
  type StationInboundSource,
  type WorkerIncomingCallRequest,
  type WorkerInboundRequest,
  type WorkerMessageClaimRequest,
  type WorkerMessageResultRequest,
} from "@/lib/calls/stationContract";
import type { WhatsappAttachment } from "./contract";

export const STATION_ACCOUNT_PREFIX = "station:";

export function stationAccountRef(stationId: string): string {
  return `${STATION_ACCOUNT_PREFIX}${stationId}`;
}

export function isStationAccountRef(unipileAccountId: string): boolean {
  return unipileAccountId.startsWith(STATION_ACCOUNT_PREFIX);
}

/** "+919876543210" → "919876543210@s.whatsapp.net". */
export function stationChatId(phone: string): string {
  return `${phone.replace(/\D/g, "")}@s.whatsapp.net`;
}

/** A user jid's number, E.164: "<digits>@c.us" / "<digits>@s.whatsapp.net" (with or without a ":device" part). Null for "@lid", groups and the rest. */
export function jidPhone(jid: string | null | undefined): string | null {
  const match = /^(\d{7,15})(?::\d+)?@(c\.us|s\.whatsapp\.net)$/.exec(jid?.trim() ?? "");
  return match ? `+${match[1]}` : null;
}

/** Chats that are not one person: groups, status updates, channels, broadcast lists. */
export function isNonPersonJid(jid: string): boolean {
  return /@(g\.us|broadcast|newsletter)$/.test(jid) || jid.startsWith("status@");
}

export type ParsedWhatsappMessageId = { fromMe: boolean | null; jid: string | null; keyId: string };

/**
 * WhatsApp Web's message id: "<true|false>_<chat jid>_<key id>" (a group's
 * carries a "_<participant>" too), as msg.id._serialized and a row's data-id
 * write it — or a bare key id. Null when there is nothing usable.
 */
export function parseWhatsappMessageId(raw: string): ParsedWhatsappMessageId | null {
  const value = raw.trim();
  if (!value) return null;
  const match = /^(true|false)_([^_]+@[^_]+)_([^_]+)(?:_.*)?$/.exec(value);
  if (match) return { fromMe: match[1] === "true", jid: match[2]!, keyId: match[3]! };
  if (/^[A-Za-z0-9.:-]{4,128}$/.test(value)) return { fromMe: null, jid: null, keyId: value };
  return null;
}

/** whatsapp_messages.unipile_message_id for a message a station saw. */
export function stationMessageKey(stationId: string, providerMessageId: string): string | null {
  const parsed = parseWhatsappMessageId(providerMessageId);
  return parsed ? `${STATION_ACCOUNT_PREFIX}${stationId}:${parsed.keyId}` : null;
}

/** The chat a station message belongs to: by number when known, else by its WhatsApp id. */
export function stationChatKey(message: { chatPhone: string | null; chatJid: string }): { unipileChatId: string; phone: string | null } {
  const phone = message.chatPhone ?? jidPhone(message.chatJid);
  if (phone) return { unipileChatId: stationChatId(phone), phone };
  return { unipileChatId: message.chatJid.trim(), phone: null };
}

/** WhatsApp's media types as whatsapp_messages attachments (the Unipile type names messagePreview knows). */
export function stationAttachments(kind: string | null | undefined): WhatsappAttachment[] {
  if (!kind || kind === "chat") return [];
  const type = kind === "image" ? "img" : kind === "ptt" || kind === "audio" ? "audio" : kind === "video" ? "video" : kind === "document" ? "file" : kind;
  return [{ id: null, type, name: null, mimeType: null }];
}

/** The echo of a station send: the oldest reserved AgentSDR message in the chat with the same text. */
export function pickStationEcho<T extends { body: string; sentAt: Date }>(candidates: readonly T[], text: string): T | null {
  const normalize = (value: string) => value.replace(/\r\n/g, "\n").trim();
  const wanted = normalize(text);
  return [...candidates]
    .filter((candidate) => normalize(candidate.body) === wanted)
    .sort((left, right) => left.sentAt.getTime() - right.sentAt.getTime())[0] ?? null;
}

// --- message jobs: what happens to one -------------------------------------------

/**
 * A job back in the queue carries the reason in `error`, prefixed with this;
 * a job that already went back once is failed the next time instead.
 */
export const RETRY_MARK = "retry: ";

export type JobState = { status: "queued" | "claimed" | "sent" | "failed"; error: string | null };

export type JobOutcome =
  | { action: "sent" }
  | { action: "requeue"; error: string }
  /** `uncertain`: it may have gone out — the reserved message is kept (marked), not removed. */
  | { action: "fail"; error: string; uncertain?: boolean }
  | { action: "ignore" };

/** The error of a claimed job whose worker never reported: it may or may not have gone out. */
export const UNCERTAIN_DELIVERY_ERROR = "Delivery uncertain: the worker did not report — check the chat before resending";

/**
 * What a worker's report does to a job. A send that worked is taken from the
 * claim, or late, after the job was failed as uncertain (it did go out); a
 * failure only from the claim it answers. A retryable failure (the worker
 * says it did not send) goes back to the queue once.
 */
export function jobOutcomeForResult(job: JobState, result: WorkerMessageResultRequest): JobOutcome {
  if (result.ok && job.status === "failed" && job.error === UNCERTAIN_DELIVERY_ERROR) return { action: "sent" };
  if (job.status === "sent" || job.status === "failed") return { action: "ignore" };
  if (result.ok) return { action: "sent" };
  if (job.status !== "claimed") return { action: "ignore" };
  const error = result.error.trim().slice(0, 500) || "The call worker could not send the message";
  // It may have gone out: kept as uncertain (its echo, if it comes, makes it sent), never requeued.
  // Workers before the flag said so only in the text.
  if (result.uncertain || /may have been sent/i.test(error)) return { action: "fail", error, uncertain: true };
  if (result.retryable && !job.error?.startsWith(RETRY_MARK)) return { action: "requeue", error: `${RETRY_MARK}${error}` };
  return { action: "fail", error };
}

/**
 * A claimed job whose worker went quiet: failed as uncertain, never requeued —
 * the worker may have sent it, and a lead must never get a message twice.
 */
export function jobOutcomeWhenStale(job: JobState): Exclude<JobOutcome, { action: "sent" }> {
  if (job.status !== "claimed") return { action: "ignore" };
  return { action: "fail", error: UNCERTAIN_DELIVERY_ERROR, uncertain: true };
}

// --- the worker's reports --------------------------------------------------------

export class StationReportError extends Error {}

function asObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new StationReportError("Expected a JSON object");
  return value as Record<string, unknown>;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: string): boolean {
  return UUID_PATTERN.test(value);
}

/** POST /api/call-worker/stations/:id/incoming — a call ringing on the number. */
export function parseIncomingCallRequest(value: unknown): WorkerIncomingCallRequest {
  const body = asObject(value);
  const workerId = typeof body.workerId === "string" ? body.workerId.trim().slice(0, 100) : "";
  if (!workerId) throw new StationReportError("workerId is required");
  const call = asObject(body.call);
  const waCallId = typeof call.waCallId === "string" ? call.waCallId.trim().slice(0, 200) : "";
  if (!waCallId) throw new StationReportError("call.waCallId is required");
  if (typeof call.at !== "number" || !Number.isFinite(call.at)) throw new StationReportError("call.at must be a time in ms");
  const phone = typeof call.phone === "string" && call.phone.trim() ? call.phone.trim().slice(0, 32) : null;
  const callerName = typeof call.callerName === "string" && call.callerName.trim() ? call.callerName.trim().slice(0, 200) : null;
  return {
    workerId,
    call: { waCallId, phone, callerName, isVideo: call.isVideo === true, isGroup: call.isGroup === true, at: call.at },
  };
}

export function parseMessageClaim(value: unknown): WorkerMessageClaimRequest {
  const body = asObject(value);
  const workerId = typeof body.workerId === "string" ? body.workerId.trim().slice(0, 100) : "";
  if (!workerId) throw new StationReportError("workerId is required");
  if (!Array.isArray(body.stations) || body.stations.length > 100 || !body.stations.every((id) => typeof id === "string" && isUuid(id))) {
    throw new StationReportError("stations must be a list of station ids");
  }
  return { workerId, stations: body.stations as string[] };
}

export function parseMessageResult(value: unknown): WorkerMessageResultRequest {
  const body = asObject(value);
  if (body.ok === true) {
    const providerMessageId = typeof body.providerMessageId === "string" && body.providerMessageId.trim() ? body.providerMessageId.trim().slice(0, 300) : null;
    const sentAt = typeof body.sentAt === "number" && Number.isFinite(body.sentAt) ? body.sentAt : Date.now();
    return { ok: true, providerMessageId, sentAt };
  }
  if (body.ok === false) {
    const error = typeof body.error === "string" ? body.error.slice(0, 500) : "The call worker could not send the message";
    return { ok: false, error, retryable: body.retryable === true, uncertain: body.uncertain === true };
  }
  throw new StationReportError("ok must be true or false");
}

const SOURCES: readonly StationInboundSource[] = ["store", "dom", "none"];

/** Drops what cannot be stored (groups, no id, no chat) rather than refusing the batch. */
export function parseInboundRequest(value: unknown, now = Date.now()): WorkerInboundRequest {
  const body = asObject(value);
  const source = SOURCES.includes(body.source as StationInboundSource) ? (body.source as StationInboundSource) : "none";
  if (!Array.isArray(body.messages)) throw new StationReportError("messages must be a list");
  if (body.messages.length > MAX_INBOUND_BATCH) throw new StationReportError(`At most ${MAX_INBOUND_BATCH} messages per report`);
  const messages: StationInboundMessage[] = [];
  for (const item of body.messages as unknown[]) {
    if (!item || typeof item !== "object") continue;
    const m = item as Record<string, unknown>;
    const providerMessageId = typeof m.providerMessageId === "string" ? m.providerMessageId.trim().slice(0, 300) : "";
    const chatJid = typeof m.chatJid === "string" ? m.chatJid.trim().slice(0, 200) : "";
    if (!providerMessageId || !parseWhatsappMessageId(providerMessageId) || !chatJid || isNonPersonJid(chatJid)) continue;
    if (m.direction !== "inbound" && m.direction !== "outbound") continue;
    const chatPhone = typeof m.chatPhone === "string" && /^\+\d{7,15}$/.test(m.chatPhone.trim()) ? m.chatPhone.trim() : null;
    // A time ahead of the server's (the browser's clock) is taken as now.
    const sentAt = typeof m.sentAt === "number" && Number.isFinite(m.sentAt) && m.sentAt > 0 ? Math.min(m.sentAt, now) : now;
    messages.push({
      providerMessageId,
      chatPhone,
      chatJid,
      chatName: typeof m.chatName === "string" && m.chatName.trim() ? m.chatName.trim().slice(0, 200) : null,
      direction: m.direction,
      text: typeof m.text === "string" ? m.text.slice(0, 10_000) : "",
      sentAt,
      kind: typeof m.kind === "string" && m.kind ? m.kind.slice(0, 40) : null,
    });
  }
  return { source, messages };
}
