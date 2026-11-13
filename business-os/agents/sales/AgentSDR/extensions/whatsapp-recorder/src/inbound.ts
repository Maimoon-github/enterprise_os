/**
 * Pure helpers for a calling station's WhatsApp messaging: reading WhatsApp's
 * message ids and chat ids, the chat rows' "[time, date] Name: " prefix, which
 * message types are kept, and the service worker's deduplicated buffer of
 * messages waiting for the call worker's next take.
 *
 * Dependency-free (only types), so wa-hook, wa-agent and the service worker
 * can all bundle it, and bun:test can run it.
 */

import type { StationInboundMessage } from "../../../src/lib/calls/stationContract";

/** A message id as WhatsApp serializes it: "true_<chat jid>_<key id>" (groups add "_<participant>"). */
export type ParsedMessageId = { fromMe: boolean; jid: string; keyId: string };

export function parseMessageId(id: string | null | undefined): ParsedMessageId | null {
  if (!id) return null;
  const match = /^(true|false)_([^_\s]+@[^_\s]+)_([^_\s]+)(?:_.*)?$/.exec(id.trim());
  if (!match) return null;
  return { fromMe: match[1] === "true", jid: match[2], keyId: match[3] };
}

/**
 * A message key's serialized id. WhatsApp Web used to carry it as
 * `_serialized`; from about 2.3000.105 (Oct 2026) the key has no such field,
 * so it is its toString(), else built from the key's own parts the way
 * WhatsApp serializes them. Null when none of these gives a valid id.
 */
export function serializedMessageId(key: {
  serialized: unknown;
  text: unknown;
  fromMe: unknown;
  remoteJid: string | null;
  keyId: unknown;
}): string | null {
  for (const candidate of [key.serialized, key.text]) {
    if (typeof candidate === "string" && parseMessageId(candidate)) return candidate.trim();
  }
  if (typeof key.fromMe !== "boolean" || !key.remoteJid || typeof key.keyId !== "string" || !key.keyId) return null;
  const built = `${key.fromMe}_${key.remoteJid}_${key.keyId}`;
  return parseMessageId(built) ? built : null;
}

/** What a message is deduplicated on: its key id (the server keys on it too), else the whole id. */
export function messageDedupeKey(providerMessageId: string): string {
  return parseMessageId(providerMessageId)?.keyId ?? providerMessageId;
}

/** "<digits>@c.us" / "<digits>@s.whatsapp.net" → "+<digits>". A "@lid", group or broadcast id has no number. */
export function jidToPhone(jid: string | null | undefined): string | null {
  const match = /^(\d{6,15})(?::\d+)?@(c\.us|s\.whatsapp\.net)$/.exec(jid?.trim() ?? "");
  return match ? `+${match[1]}` : null;
}

/** Group chats, status updates, broadcast lists and channels — never messages from a lead. */
export function isNonPersonalJid(jid: string | null | undefined): boolean {
  const value = jid?.trim() ?? "";
  return !value || /@g\.us$/.test(value) || /@broadcast$/.test(value) || /@newsletter$/.test(value) || /@call$/.test(value);
}

/** Message types that are something a person sent; everything else (notifications, protocol, revokes, call logs…) is skipped. */
const KEPT_TYPES = new Set(["chat", "image", "video", "ptt", "audio", "document", "sticker", "location", "vcard", "multi_vcard"]);

export function isKeptMessageType(type: string | null | undefined): boolean {
  return KEPT_TYPES.has(type ?? "");
}

/** A message's text: the body for a text message, the caption for media. */
export function messageText(type: string, body: unknown, caption: unknown): string {
  if (type === "chat") return typeof body === "string" ? body : "";
  return typeof caption === "string" ? caption : "";
}

/** The fields wa-hook reads off one of WhatsApp's own message models. */
export type StoreMessageFields = {
  id: string | null;
  fromMe: boolean;
  /** The chat's jid ("<digits>@c.us", "<id>@lid", "<group>@g.us"). */
  chatJid: string | null;
  /** The number behind a "@lid" chat, when WhatsApp knows it (digits, any format). */
  lidPhone: string | null;
  /** Seconds, as msg.t. */
  t: number | null;
  type: string | null;
  body: unknown;
  caption: unknown;
  chatName: string | null;
};

/** One of WhatsApp's message models as a StationInboundMessage, or null when it is not one to keep. */
export function storeMessage(fields: StoreMessageFields, now = Date.now()): StationInboundMessage | null {
  if (!fields.id || !fields.chatJid || isNonPersonalJid(fields.chatJid)) return null;
  const type = fields.type ?? "";
  if (!isKeptMessageType(type)) return null;
  const lidDigits = fields.lidPhone?.replace(/\D/g, "") ?? "";
  return {
    providerMessageId: fields.id,
    chatPhone: jidToPhone(fields.chatJid) ?? (lidDigits.length >= 6 ? `+${lidDigits}` : null),
    chatJid: fields.chatJid,
    chatName: fields.chatName?.trim() || null,
    direction: fields.fromMe ? "outbound" : "inbound",
    text: messageText(type, fields.body, fields.caption),
    sentAt: fields.t && Number.isFinite(fields.t) ? Math.round(fields.t * 1000) : now,
    kind: type === "chat" ? null : type,
  };
}

/**
 * A chat row's data-pre-plain-text, "[10:42, 27/10/2026] Name: " (or
 * "[10:42 am, 10/27/2026] Name: "): who wrote it and when. The date's order
 * follows the browser's locale, so an ambiguous day/month is read whichever
 * way lands closest to `now` without being in the future.
 */
export function parsePrePlainText(value: string | null | undefined, now = Date.now()): { sender: string | null; sentAt: number | null } {
  const match = /^\s*\[([^\]]+)\]\s*(.*?):\s*$/.exec(value ?? "");
  if (!match) return { sender: null, sentAt: null };
  const sender = match[2].trim() || null;
  const time = /(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?\s*([ap]\.?\s?m\.?)?/i.exec(match[1]);
  const date = /(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})/.exec(match[1]);
  if (!time || !date) return { sender, sentAt: null };
  let hours = Number(time[1]);
  const minutes = Number(time[2]);
  const seconds = time[3] ? Number(time[3]) : 0;
  const meridiem = time[4]?.toLowerCase().replace(/[^ap]/g, "");
  if (meridiem === "p" && hours < 12) hours += 12;
  if (meridiem === "a" && hours === 12) hours = 0;

  const [a, b, c] = [Number(date[1]), Number(date[2]), Number(date[3])];
  const candidates: { year: number; month: number; day: number }[] = [];
  if (date[1].length === 4) candidates.push({ year: a, month: b, day: c });
  else {
    const year = c < 100 ? 2000 + c : c;
    candidates.push({ year, month: b, day: a }, { year, month: a, day: b });
  }
  let best: number | null = null;
  for (const { year, month, day } of candidates) {
    if (month < 1 || month > 12 || day < 1 || day > 31) continue;
    const at = new Date(year, month - 1, day, hours, minutes, seconds).getTime();
    if (new Date(at).getDate() !== day) continue; // 31/02 and the like
    if (at > now + 60_000) continue;
    if (best === null || now - at < now - best) best = at;
  }
  return { sender, sentAt: best };
}

/** The service worker's buffer of messages for the next take, and the keys it has already seen. */
export type InboundBuffer = { messages: StationInboundMessage[]; seen: string[] };

export const INBOUND_BUFFER_MAX = 500;
export const INBOUND_SEEN_MAX = 500;

/**
 * Adds messages not seen before (by key id) to the buffer. The seen list is
 * bounded (oldest dropped first), and so is the buffer — its oldest messages
 * drop when the worker stops taking them.
 */
export function mergeInbound(
  buffer: InboundBuffer,
  incoming: StationInboundMessage[],
  limits = { buffer: INBOUND_BUFFER_MAX, seen: INBOUND_SEEN_MAX },
): InboundBuffer & { added: number } {
  const seen = new Set(buffer.seen);
  const order = [...buffer.seen];
  const messages = [...buffer.messages];
  let added = 0;
  for (const message of incoming) {
    if (!message?.providerMessageId) continue;
    const key = messageDedupeKey(message.providerMessageId);
    if (seen.has(key)) continue;
    seen.add(key);
    order.push(key);
    messages.push(message);
    added++;
  }
  return { messages: messages.slice(-limits.buffer), seen: order.slice(-limits.seen), added };
}
