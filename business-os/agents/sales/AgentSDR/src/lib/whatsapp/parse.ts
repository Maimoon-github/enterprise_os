import { createHash } from "node:crypto";
import {
  bareWhatsappJid,
  isWhatsappGroupId,
  phoneFromProviderId,
} from "@/services/unipile.whatsapp";
import type { WhatsappAttachment, WhatsappMessageOrigin } from "./contract";

/**
 * Reading what Unipile sends — webhook deliveries and the chat / message
 * objects its list endpoints return — into plain records. Pure and
 * defensive: Unipile's WhatsApp payloads are not fully documented, so every
 * field is optional here and a payload that cannot be understood becomes an
 * "ignore" with a reason (logged on the delivery), never a throw.
 *
 * Webhook payload fields relied on (the same "messaging" webhook shape the
 * LinkedIn route reads): event, account_type, account_id, chat_id,
 * message_id, message, timestamp, is_sender, sender.attendee_provider_id,
 * sender.attendee_name, attendees[].attendee_provider_id / attendee_name,
 * account_info.user_id, attachments[]. Group markers accepted: is_group,
 * provider_chat_id / chat_provider_id ending "@g.us", or more than one
 * counterparty among the attendees.
 */

type Json = Record<string, unknown>;

function asObject(value: unknown): Json | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Json) : null;
}

function str(value: unknown): string | null {
  if (typeof value === "string") return value.trim() ? value.trim() : null;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return null;
}

/** Unipile uses both booleans and 0/1 for flags. */
function flag(value: unknown): boolean {
  return value === true || value === 1 || value === "1" || value === "true";
}

function date(value: unknown): Date | null {
  if (typeof value !== "string" && typeof value !== "number") return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function parseAttachments(value: unknown): WhatsappAttachment[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const attachment = asObject(item);
    if (!attachment) return [];
    return [{
      id: str(attachment.id),
      type: str(attachment.type),
      name: str(attachment.file_name) ?? str(attachment.name),
      mimeType: str(attachment.mimetype) ?? str(attachment.mime_type) ?? str(attachment.mimeType),
    }];
  });
}

/** A one-line preview of a message for the chat list. */
export function messagePreview(body: string, attachments: WhatsappAttachment[]): string {
  const text = body.replace(/\s+/g, " ").trim();
  if (text) return text.length > 200 ? `${text.slice(0, 199)}…` : text;
  const type = attachments[0]?.type;
  if (!type) return "";
  return type === "img" ? "Photo" : type === "audio" ? "Audio" : type === "video" ? "Video" : "Attachment";
}

// --- webhook -------------------------------------------------------------------

export type ParsedWhatsappMessageEvent = {
  kind: "message";
  unipileAccountId: string;
  unipileChatId: string;
  unipileMessageId: string;
  /** true for a message the account itself sent (from AgentSDR or the phone). */
  isSender: boolean;
  /** The lead's WhatsApp id: "<digits>@s.whatsapp.net" (or "…@lid", which carries no number). */
  counterpartyProviderId: string;
  counterpartyPhone: string | null;
  counterpartyName: string | null;
  body: string;
  attachments: WhatsappAttachment[];
  sentAt: Date;
};

export type ParsedWhatsappStatusEvent = {
  kind: "status";
  status: "read" | "delivered";
  unipileAccountId: string | null;
  unipileMessageId: string;
  at: Date;
};

export type ParsedWhatsappWebhook =
  | ParsedWhatsappMessageEvent
  | ParsedWhatsappStatusEvent
  | { kind: "ignore"; reason: string };

const STATUS_EVENTS: Record<string, ParsedWhatsappStatusEvent["status"]> = {
  message_read: "read",
  message_delivered: "delivered",
};

type Attendee = { providerId: string | null; name: string | null; phone: string | null };

/**
 * A number from a "+919876543210" string, or null. WhatsApp now addresses
 * most people by a privacy id ("…@lid") that carries no number, so the
 * number comes from the public identifier ("919876543210@s.whatsapp.net")
 * or the attendee's specifics.phone_number — seen on real Unipile chats,
 * 30 Sep 2026.
 */
function phoneFromValue(value: unknown): string | null {
  const text = str(value);
  if (!text) return null;
  const fromId = phoneFromProviderId(text);
  if (fromId) return fromId;
  const digits = text.replace(/[\s()-]/g, "");
  return /^\+?\d{8,15}$/.test(digits) ? `+${digits.replace(/^\+/, "")}` : null;
}

function attendee(value: unknown): Attendee | null {
  const object = asObject(value);
  if (!object) return null;
  const specifics = asObject(object.attendee_specifics) ?? asObject(object.specifics);
  return {
    providerId: str(object.attendee_provider_id) ?? str(object.provider_id),
    name: str(object.attendee_name) ?? str(object.name),
    phone:
      phoneFromValue(object.attendee_public_identifier) ??
      phoneFromValue(object.public_identifier) ??
      phoneFromValue(specifics?.phone_number) ??
      phoneFromProviderId(str(object.attendee_provider_id) ?? str(object.provider_id)),
  };
}

export function parseWhatsappWebhook(payload: unknown, now = new Date()): ParsedWhatsappWebhook {
  const body = asObject(payload);
  if (!body) return { kind: "ignore", reason: "payload is not a JSON object" };

  const event = str(body.event) ?? "unknown";
  const accountType = str(body.account_type);
  if (accountType && accountType.toUpperCase() !== "WHATSAPP") {
    return { kind: "ignore", reason: `account_type ${accountType} is not WHATSAPP` };
  }
  const unipileAccountId = str(body.account_id);
  const unipileMessageId = str(body.message_id) ?? str(body.id);

  const statusEvent = STATUS_EVENTS[event];
  if (statusEvent) {
    if (!unipileMessageId) return { kind: "ignore", reason: `${event} without a message_id` };
    return {
      kind: "status",
      status: statusEvent,
      unipileAccountId,
      unipileMessageId,
      at: date(body.timestamp) ?? now,
    };
  }

  if (event !== "message_received") return { kind: "ignore", reason: `event "${event}" is not handled` };
  // Status events may omit account_type; a message must carry it, so a
  // LinkedIn message can never be read as WhatsApp.
  if (!accountType) return { kind: "ignore", reason: "message_received without account_type" };
  if (!unipileAccountId) return { kind: "ignore", reason: "message_received without account_id" };
  const unipileChatId = str(body.chat_id);
  if (!unipileChatId) return { kind: "ignore", reason: "message_received without chat_id" };
  if (!unipileMessageId) return { kind: "ignore", reason: "message_received without message_id" };

  const providerChatId = str(body.provider_chat_id) ?? str(body.chat_provider_id);
  if (flag(body.is_group) || isWhatsappGroupId(providerChatId)) {
    return { kind: "ignore", reason: "group chat" };
  }

  const isSender = flag(body.is_sender);
  const sender = attendee(body.sender);
  const ownId = bareWhatsappJid(str(asObject(body.account_info)?.user_id));
  const senderId = bareWhatsappJid(sender?.providerId);
  if (isWhatsappGroupId(sender?.providerId)) return { kind: "ignore", reason: "group chat" };

  // The attendees other than the account and the sender (on an echo the
  // sender is the account). In a one-to-one chat that leaves the lead on an
  // echo, and nobody on an inbound message — or the account itself when the
  // payload does not say which id is the account's. More is a group.
  const others = (Array.isArray(body.attendees) ? body.attendees : [])
    .map(attendee)
    .filter((item): item is Attendee => Boolean(item?.providerId))
    .filter((item) => {
      const id = bareWhatsappJid(item.providerId);
      return id !== ownId && id !== senderId;
    });
  if (others.some((item) => isWhatsappGroupId(item.providerId))) return { kind: "ignore", reason: "group chat" };
  // A one-to-one chat has two attendees, the account and the lead. Counted,
  // not compared: with privacy ids the account's own id and an attendee's may
  // not be written the same way, so "everyone but us" can over-count.
  const attendeeCount = new Set(
    (Array.isArray(body.attendees) ? body.attendees : [])
      .map(attendee)
      .map((item) => item?.providerId ?? item?.phone)
      .filter(Boolean),
  ).size;
  if (attendeeCount > 2) return { kind: "ignore", reason: "group chat (several counterparties)" };

  // The lead: the sender of an inbound message; on an echo (is_sender) the
  // attendee that isn't the account — mirroring the LinkedIn route. A 1:1
  // chat's provider id is the lead's own id, the last resort for both.
  let counterparty: Attendee | null;
  if (isSender) {
    counterparty = others[0] ?? null;
  } else {
    counterparty = sender?.providerId && senderId !== ownId ? sender : null;
  }
  if (!counterparty?.providerId && providerChatId && !isWhatsappGroupId(providerChatId)) {
    counterparty = { providerId: providerChatId, name: null, phone: phoneFromProviderId(providerChatId) };
  }
  if (!counterparty?.providerId) {
    return { kind: "ignore", reason: isSender ? "echo without a counterparty attendee" : "message without a sender" };
  }

  const counterpartyProviderId = bareWhatsappJid(counterparty.providerId) ?? counterparty.providerId;
  return {
    kind: "message",
    unipileAccountId,
    unipileChatId,
    unipileMessageId,
    isSender,
    counterpartyProviderId,
    counterpartyPhone: counterparty.phone ?? phoneFromProviderId(counterpartyProviderId),
    counterpartyName: counterparty.name,
    body: typeof body.message === "string" ? body.message : "",
    attachments: parseAttachments(body.attachments),
    sentAt: date(body.timestamp) ?? now,
  };
}

/**
 * The delivery's identity in the webhook ledger (WebhookEvent.providerEventKey),
 * collapsing Unipile's retries. Prefixed "whatsapp:" so it never collides
 * with the LinkedIn route's key for the same Unipile message, should one
 * messaging webhook post to both.
 */
export function whatsappWebhookEventKey(payload: unknown): string {
  const body = asObject(payload) ?? {};
  const event = str(body.event) ?? "unknown";
  const accountId = str(body.account_id);
  const messageId = str(body.message_id) ?? str(body.id);
  if (accountId && messageId) return `whatsapp:${event}:v1:${accountId}:${messageId}`;
  const digest = createHash("sha256").update(JSON.stringify(payload) ?? "null").digest("hex");
  return `whatsapp:${event}:payload-sha256:${digest}`;
}

// --- where a message came from -----------------------------------------------------

/** How long after an AgentSDR send its echo may arrive and still be recognised. */
export const ECHO_MATCH_WINDOW_MS = 2 * 60 * 1000;

export type PendingSend = { id: string; body: string; sentAt: Date };

function sameText(left: string, right: string): boolean {
  const normalize = (value: string) => value.replace(/\r\n/g, "\n").trim();
  return normalize(left) === normalize(right);
}

/**
 * The AgentSDR send an echo belongs to: one stored without a Unipile id yet
 * (Unipile's echo can beat its own send response), same text, within the
 * window. The oldest wins, so two identical sends pair up in order.
 */
export function pickPendingSend(
  candidates: readonly PendingSend[],
  echo: { body: string },
  now: Date,
  windowMs = ECHO_MATCH_WINDOW_MS,
): PendingSend | null {
  const matches = candidates
    .filter((candidate) => sameText(candidate.body, echo.body))
    .filter((candidate) => Math.abs(now.getTime() - candidate.sentAt.getTime()) <= windowMs)
    .sort((left, right) => left.sentAt.getTime() - right.sentAt.getTime());
  return matches[0] ?? null;
}

export type IngestDecision =
  /** A row already has this Unipile id: a retried delivery, or the echo of our own send. */
  | { action: "duplicate" }
  /** The echo of an AgentSDR send still waiting for its id: attach it. */
  | { action: "attach"; pendingId: string }
  /** A new message to store, from the lead or typed on the rep's phone. */
  | { action: "store"; origin: WhatsappMessageOrigin };

export function decideIngest(input: {
  isSender: boolean;
  alreadyStored: boolean;
  pendingMatch: PendingSend | null;
}): IngestDecision {
  if (input.alreadyStored) return { action: "duplicate" };
  if (!input.isSender) return { action: "store", origin: "lead" };
  if (input.pendingMatch) return { action: "attach", pendingId: input.pendingMatch.id };
  return { action: "store", origin: "phone" };
}

// --- Unipile list objects (backfill) ---------------------------------------------------

export type UnipileChatRecord = {
  unipileChatId: string;
  providerId: string | null;
  phone: string | null;
  name: string | null;
  isGroup: boolean;
  lastMessageAt: Date | null;
  unreadCount: number;
};

/** A Unipile Chat object (GET /chats). Null when it has no id. */
export function mapUnipileChat(item: unknown): UnipileChatRecord | null {
  const chat = asObject(item);
  const unipileChatId = str(chat?.id);
  if (!chat || !unipileChatId) return null;
  const chatProviderId = str(chat.provider_id);
  const attendeeProviderId = str(chat.attendee_provider_id);
  // type 0 is a one-to-one chat; 1 and 2 are groups and channels.
  const type = typeof chat.type === "number" ? chat.type : null;
  const isGroup = (type !== null && type !== 0) || isWhatsappGroupId(chatProviderId) || isWhatsappGroupId(attendeeProviderId);
  const providerId = bareWhatsappJid(attendeeProviderId ?? chatProviderId);
  const unread = Number(chat.unread_count);
  return {
    unipileChatId,
    providerId: isGroup ? null : providerId,
    // The public identifier carries the number when the provider id is a
    // privacy id ("…@lid").
    phone: isGroup ? null : (phoneFromValue(chat.attendee_public_identifier) ?? phoneFromProviderId(providerId)),
    name: str(chat.name),
    isGroup,
    lastMessageAt: date(chat.timestamp),
    unreadCount: Number.isInteger(unread) && unread > 0 ? unread : 0,
  };
}

export type UnipileMessageRecord = {
  unipileMessageId: string;
  isSender: boolean;
  body: string;
  attachments: WhatsappAttachment[];
  sentAt: Date;
  /** Known only as a flag, so stamped with the send time. Outbound only. */
  deliveredAt: Date | null;
  readAt: Date | null;
};

/**
 * A Unipile Message object (GET /chats/:id/messages). Null when it has no
 * id or time, or is not a real message (a system event, hidden or deleted).
 */
export function mapUnipileMessage(item: unknown): UnipileMessageRecord | null {
  const message = asObject(item);
  const unipileMessageId = str(message?.id);
  const sentAt = date(message?.timestamp);
  if (!message || !unipileMessageId || !sentAt) return null;
  if (flag(message.is_event) || flag(message.hidden) || flag(message.deleted)) return null;
  const isSender = flag(message.is_sender);
  const body = typeof message.text === "string" ? message.text : "";
  const attachments = parseAttachments(message.attachments);
  if (!body.trim() && attachments.length === 0) return null;
  return {
    unipileMessageId,
    isSender,
    body,
    attachments,
    sentAt,
    deliveredAt: isSender && (flag(message.delivered) || flag(message.seen)) ? sentAt : null,
    readAt: isSender && flag(message.seen) ? sentAt : null,
  };
}
