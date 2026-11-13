import { describe, expect, test } from "bun:test";
import {
  decideIngest,
  mapUnipileChat,
  mapUnipileMessage,
  messagePreview,
  parseWhatsappWebhook,
  pickPendingSend,
  whatsappWebhookEventKey,
} from "./parse";

const NOW = new Date("2026-09-30T10:00:00.000Z");
const ACCOUNT_JID = "919800000001@s.whatsapp.net";
const LEAD_JID = "14155552671@s.whatsapp.net";

/** A message_received delivery shaped like the LinkedIn route's, for a WhatsApp account. */
function delivery(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    event: "message_received",
    account_type: "WHATSAPP",
    account_id: "acc_wa_1",
    account_info: { type: "WHATSAPP", user_id: ACCOUNT_JID },
    chat_id: "chat_1",
    message_id: "msg_1",
    message: "Hi, is this about the demo?",
    timestamp: "2026-09-30T09:59:58.000Z",
    is_sender: false,
    sender: { attendee_provider_id: LEAD_JID, attendee_name: "Jane Lead" },
    attendees: [
      { attendee_provider_id: LEAD_JID, attendee_name: "Jane Lead" },
      { attendee_provider_id: ACCOUNT_JID, attendee_name: "Rep" },
    ],
    ...overrides,
  };
}

describe("parseWhatsappWebhook", () => {
  test("reads an inbound message from the lead", () => {
    const parsed = parseWhatsappWebhook(delivery(), NOW);
    expect(parsed).toEqual({
      kind: "message",
      unipileAccountId: "acc_wa_1",
      unipileChatId: "chat_1",
      unipileMessageId: "msg_1",
      isSender: false,
      counterpartyProviderId: LEAD_JID,
      counterpartyPhone: "+14155552671",
      counterpartyName: "Jane Lead",
      body: "Hi, is this about the demo?",
      attachments: [],
      sentAt: new Date("2026-09-30T09:59:58.000Z"),
    });
  });

  test("an echo (typed on the phone or sent by AgentSDR) resolves the lead from the attendees, not the sender", () => {
    const parsed = parseWhatsappWebhook(delivery({
      is_sender: true,
      message: "Yes — sending the deck now",
      sender: { attendee_provider_id: ACCOUNT_JID, attendee_name: "Rep" },
    }), NOW);
    expect(parsed.kind).toBe("message");
    if (parsed.kind !== "message") return;
    expect(parsed.isSender).toBe(true);
    expect(parsed.counterpartyProviderId).toBe(LEAD_JID);
    expect(parsed.counterpartyPhone).toBe("+14155552671");
    expect(parsed.counterpartyName).toBe("Jane Lead");
  });

  test("an echo whose own id carries a device suffix still finds the lead", () => {
    const parsed = parseWhatsappWebhook(delivery({
      is_sender: true,
      account_info: { user_id: "919800000001:17@s.whatsapp.net" },
      sender: { attendee_provider_id: "919800000001:17@s.whatsapp.net" },
    }), NOW);
    expect(parsed.kind === "message" && parsed.counterpartyPhone).toBe("+14155552671");
  });

  test("an echo without a counterparty attendee falls back to the chat's provider id, else is ignored", () => {
    const base = { is_sender: true, sender: { attendee_provider_id: ACCOUNT_JID }, attendees: [] };
    const withChatId = parseWhatsappWebhook(delivery({ ...base, provider_chat_id: LEAD_JID }), NOW);
    expect(withChatId.kind === "message" && withChatId.counterpartyPhone).toBe("+14155552671");
    expect(parseWhatsappWebhook(delivery(base), NOW)).toEqual({ kind: "ignore", reason: "echo without a counterparty attendee" });
  });

  test("group chats are ignored whichever way they are marked", () => {
    expect(parseWhatsappWebhook(delivery({ is_group: true }), NOW).kind).toBe("ignore");
    expect(parseWhatsappWebhook(delivery({ provider_chat_id: "120363025@g.us" }), NOW).kind).toBe("ignore");
    expect(parseWhatsappWebhook(delivery({ sender: { attendee_provider_id: "120363025@g.us" } }), NOW).kind).toBe("ignore");
    const threePeople = delivery({
      attendees: [
        { attendee_provider_id: LEAD_JID },
        { attendee_provider_id: ACCOUNT_JID },
        { attendee_provider_id: "447700900123@s.whatsapp.net" },
      ],
    });
    expect(parseWhatsappWebhook(threePeople, NOW).kind).toBe("ignore");
  });

  test("another provider's event is ignored", () => {
    expect(parseWhatsappWebhook(delivery({ account_type: "LINKEDIN" }), NOW)).toEqual({
      kind: "ignore",
      reason: "account_type LINKEDIN is not WHATSAPP",
    });
  });

  test("missing fields are ignored with a reason, never thrown", () => {
    expect(parseWhatsappWebhook(null, NOW).kind).toBe("ignore");
    expect(parseWhatsappWebhook("text", NOW).kind).toBe("ignore");
    for (const field of ["account_id", "chat_id", "message_id", "account_type"]) {
      const parsed = parseWhatsappWebhook(delivery({ [field]: undefined }), NOW);
      expect(parsed.kind).toBe("ignore");
    }
    expect(parseWhatsappWebhook(delivery({ sender: undefined, attendees: undefined }), NOW)).toEqual({
      kind: "ignore",
      reason: "message without a sender",
    });
    expect(parseWhatsappWebhook(delivery({ event: "message_reaction" }), NOW).kind).toBe("ignore");
  });

  test("a message with no text keeps its attachments and falls back to now for a bad timestamp", () => {
    const parsed = parseWhatsappWebhook(delivery({
      message: null,
      timestamp: "not a date",
      attachments: [{ id: "att_1", type: "img", mimetype: "image/jpeg", file_name: "photo.jpg" }],
    }), NOW);
    expect(parsed.kind === "message" && parsed.body).toBe("");
    expect(parsed.kind === "message" && parsed.sentAt).toEqual(NOW);
    expect(parsed.kind === "message" && parsed.attachments).toEqual([
      { id: "att_1", type: "img", name: "photo.jpg", mimeType: "image/jpeg" },
    ]);
  });

  test("a privacy id (@lid) is kept as the provider id with no phone", () => {
    const parsed = parseWhatsappWebhook(delivery({
      sender: { attendee_provider_id: "207716110643219@lid", attendee_name: "Jane" },
      attendees: [{ attendee_provider_id: "207716110643219@lid" }, { attendee_provider_id: ACCOUNT_JID }],
    }), NOW);
    expect(parsed.kind === "message" && parsed.counterpartyProviderId).toBe("207716110643219@lid");
    expect(parsed.kind === "message" && parsed.counterpartyPhone).toBeNull();
  });

  test("read and delivered receipts identify the message", () => {
    expect(parseWhatsappWebhook({ event: "message_read", account_id: "acc_wa_1", message_id: "msg_1", timestamp: "2026-09-30T09:00:00Z" }, NOW)).toEqual({
      kind: "status",
      status: "read",
      unipileAccountId: "acc_wa_1",
      unipileMessageId: "msg_1",
      at: new Date("2026-09-30T09:00:00Z"),
    });
    const delivered = parseWhatsappWebhook({ event: "message_delivered", account_type: "WHATSAPP", message_id: "msg_2" }, NOW);
    expect(delivered).toEqual({ kind: "status", status: "delivered", unipileAccountId: null, unipileMessageId: "msg_2", at: NOW });
    expect(parseWhatsappWebhook({ event: "message_read" }, NOW).kind).toBe("ignore");
  });
});

describe("whatsappWebhookEventKey", () => {
  test("keys a message by event, account and message id, apart from the LinkedIn route's keys", () => {
    expect(whatsappWebhookEventKey(delivery())).toBe("whatsapp:message_received:v1:acc_wa_1:msg_1");
    expect(whatsappWebhookEventKey({ event: "message_read", account_id: "acc_wa_1", message_id: "msg_1" }))
      .toBe("whatsapp:message_read:v1:acc_wa_1:msg_1");
  });

  test("falls back to a payload digest", () => {
    const key = whatsappWebhookEventKey({ event: "x" });
    expect(key).toMatch(/^whatsapp:x:payload-sha256:[0-9a-f]{64}$/);
    expect(whatsappWebhookEventKey({ event: "x" })).toBe(key);
  });
});

describe("origin decision", () => {
  const pending = { id: "row_1", body: "Following up on our call", sentAt: new Date(NOW.getTime() - 5_000) };

  test("inbound is the lead's", () => {
    expect(decideIngest({ isSender: false, alreadyStored: false, pendingMatch: null })).toEqual({ action: "store", origin: "lead" });
  });

  test("a stored Unipile id is a no-op, inbound retry or echo alike", () => {
    expect(decideIngest({ isSender: true, alreadyStored: true, pendingMatch: pending })).toEqual({ action: "duplicate" });
    expect(decideIngest({ isSender: false, alreadyStored: true, pendingMatch: null })).toEqual({ action: "duplicate" });
  });

  test("the echo of an AgentSDR send waiting for its id attaches to it", () => {
    expect(decideIngest({ isSender: true, alreadyStored: false, pendingMatch: pending })).toEqual({ action: "attach", pendingId: "row_1" });
  });

  test("an echo AgentSDR did not send was typed on the phone", () => {
    expect(decideIngest({ isSender: true, alreadyStored: false, pendingMatch: null })).toEqual({ action: "store", origin: "phone" });
  });

  test("a pending send matches on the same text within two minutes, oldest first", () => {
    const older = { id: "row_0", body: "Following up on our call\n", sentAt: new Date(NOW.getTime() - 30_000) };
    expect(pickPendingSend([pending, older], { body: " Following up on our call" }, NOW)?.id).toBe("row_0");
    expect(pickPendingSend([pending], { body: "Something else" }, NOW)).toBeNull();
    const stale = { ...pending, sentAt: new Date(NOW.getTime() - 3 * 60_000) };
    expect(pickPendingSend([stale], { body: pending.body }, NOW)).toBeNull();
  });
});

describe("Unipile list objects", () => {
  test("maps a one-to-one chat", () => {
    expect(mapUnipileChat({
      object: "Chat",
      id: "chat_1",
      account_id: "acc_wa_1",
      account_type: "WHATSAPP",
      provider_id: LEAD_JID,
      attendee_provider_id: LEAD_JID,
      name: "Jane Lead",
      type: 0,
      timestamp: "2026-09-29T18:04:11.000Z",
      unread_count: 2,
      archived: 0,
      read_only: 0,
    })).toEqual({
      unipileChatId: "chat_1",
      providerId: LEAD_JID,
      phone: "+14155552671",
      name: "Jane Lead",
      isGroup: false,
      lastMessageAt: new Date("2026-09-29T18:04:11.000Z"),
      unreadCount: 2,
    });
  });

  test("flags a group chat and drops a chat without an id", () => {
    const group = mapUnipileChat({ id: "chat_g", provider_id: "120363025@g.us", name: "Team", type: 1, timestamp: null, unread_count: 0 });
    expect(group?.isGroup).toBe(true);
    expect(group?.phone).toBeNull();
    expect(mapUnipileChat({ name: "no id" })).toBeNull();
    expect(mapUnipileChat("nope")).toBeNull();
  });

  test("maps messages, stamping receipts on outbound ones", () => {
    expect(mapUnipileMessage({
      object: "Message",
      id: "msg_9",
      chat_id: "chat_1",
      sender_id: ACCOUNT_JID,
      text: "Sent from my phone",
      timestamp: "2026-09-29T18:04:11.000Z",
      is_sender: 1,
      attachments: [],
      seen: 1,
      delivered: 1,
      hidden: 0,
      deleted: 0,
      is_event: 0,
    })).toEqual({
      unipileMessageId: "msg_9",
      isSender: true,
      body: "Sent from my phone",
      attachments: [],
      sentAt: new Date("2026-09-29T18:04:11.000Z"),
      deliveredAt: new Date("2026-09-29T18:04:11.000Z"),
      readAt: new Date("2026-09-29T18:04:11.000Z"),
    });
    const inbound = mapUnipileMessage({ id: "msg_10", text: "hello", timestamp: "2026-09-29T18:05:00.000Z", is_sender: 0, seen: 1 });
    expect(inbound?.isSender).toBe(false);
    expect(inbound?.readAt).toBeNull();
  });

  test("drops events, hidden, deleted, empty and undated messages", () => {
    const base = { id: "m", text: "x", timestamp: "2026-09-29T18:05:00.000Z" };
    expect(mapUnipileMessage({ ...base, is_event: 1 })).toBeNull();
    expect(mapUnipileMessage({ ...base, hidden: 1 })).toBeNull();
    expect(mapUnipileMessage({ ...base, deleted: 1 })).toBeNull();
    expect(mapUnipileMessage({ ...base, text: "" })).toBeNull();
    expect(mapUnipileMessage({ ...base, timestamp: undefined })).toBeNull();
    expect(mapUnipileMessage({ ...base, text: null, attachments: [{ id: "a", type: "audio" }] })?.attachments).toHaveLength(1);
  });
});

describe("messagePreview", () => {
  test("collapses whitespace, truncates, and names a bare attachment", () => {
    expect(messagePreview("  hello\n\nthere ", [])).toBe("hello there");
    expect(messagePreview("x".repeat(300), [])).toHaveLength(200);
    expect(messagePreview("", [{ id: null, type: "img", name: null, mimeType: null }])).toBe("Photo");
    expect(messagePreview("", [])).toBe("");
  });
});

describe("privacy ids (…@lid), as real Unipile WhatsApp chats carry them", () => {
  test("a chat takes its number from the public identifier", () => {
    const chat = mapUnipileChat({
      id: "chat-lid",
      type: 0,
      provider_id: "123456789012345@lid",
      attendee_provider_id: "123456789012345@lid",
      attendee_public_identifier: "919876543210@s.whatsapp.net",
      timestamp: "2026-09-30T10:00:00.000Z",
      unread_count: 0,
    });
    expect(chat?.phone).toBe("+919876543210");
    expect(chat?.isGroup).toBe(false);
  });

  test("an inbound message takes the sender's number from their public identifier or specifics", () => {
    const parsed = parseWhatsappWebhook({
      event: "message_received",
      account_type: "WHATSAPP",
      account_id: "acc",
      chat_id: "chat-lid",
      message_id: "m-lid",
      message: "hi",
      is_sender: false,
      timestamp: "2026-09-30T10:00:00.000Z",
      account_info: { user_id: "15555550123@s.whatsapp.net" },
      sender: { attendee_provider_id: "123456789012345@lid", attendee_name: "Lead", attendee_specifics: { phone_number: "+919876543210" } },
      attendees: [
        { attendee_provider_id: "999999999999999@lid", attendee_name: "Rep" },
        { attendee_provider_id: "123456789012345@lid", attendee_name: "Lead" },
      ],
    });
    expect(parsed.kind).toBe("message");
    if (parsed.kind === "message") expect(parsed.counterpartyPhone).toBe("+919876543210");
  });

  test("two attendees written in different id forms are still one-to-one, not a group", () => {
    const parsed = parseWhatsappWebhook({
      event: "message_received",
      account_type: "WHATSAPP",
      account_id: "acc",
      chat_id: "chat-lid",
      message_id: "m-echo",
      message: "sent from phone",
      is_sender: true,
      timestamp: "2026-09-30T10:00:00.000Z",
      account_info: { user_id: "15555550123@s.whatsapp.net" },
      sender: { attendee_provider_id: "999999999999999@lid" },
      attendees: [
        { attendee_provider_id: "999999999999999@lid" },
        { attendee_provider_id: "123456789012345@lid", attendee_public_identifier: "919876543210@s.whatsapp.net" },
      ],
    });
    expect(parsed.kind).toBe("message");
    if (parsed.kind === "message") expect(parsed.counterpartyPhone).toBe("+919876543210");
  });
});
