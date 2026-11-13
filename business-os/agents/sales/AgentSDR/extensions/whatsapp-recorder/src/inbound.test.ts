import { describe, expect, test } from "bun:test";
import type { StationInboundMessage } from "../../../src/lib/calls/stationContract";
import {
  serializedMessageId,
  isKeptMessageType,
  isNonPersonalJid,
  jidToPhone,
  mergeInbound,
  messageDedupeKey,
  parseMessageId,
  parsePrePlainText,
  storeMessage,
  type StoreMessageFields,
} from "./inbound";

describe("parseMessageId", () => {
  test("reads a one-to-one message id", () => {
    expect(parseMessageId("true_919876543210@c.us_3EB0A1B2C3D4E5F6")).toEqual({
      fromMe: true,
      jid: "919876543210@c.us",
      keyId: "3EB0A1B2C3D4E5F6",
    });
    expect(parseMessageId("false_123456789012345@lid_ABCDEF")).toEqual({ fromMe: false, jid: "123456789012345@lid", keyId: "ABCDEF" });
  });
  test("reads a group message id, participant and all", () => {
    expect(parseMessageId("false_120363000000000000@g.us_3EB0FF_919876543210@c.us")).toEqual({
      fromMe: false,
      jid: "120363000000000000@g.us",
      keyId: "3EB0FF",
    });
  });
  test("refuses anything else", () => {
    for (const bad of [null, undefined, "", "3EB0FF", "maybe_919876543210@c.us_3EB0", "true_919876543210_3EB0"]) {
      expect(parseMessageId(bad)).toBeNull();
    }
  });
  test("dedupes on the key id", () => {
    expect(messageDedupeKey("true_919876543210@c.us_KEY1")).toBe("KEY1");
    expect(messageDedupeKey("true_55555@lid_KEY1")).toBe("KEY1");
    expect(messageDedupeKey("KEY2")).toBe("KEY2");
  });
});

describe("serializedMessageId", () => {
  const parts = { fromMe: false, remoteJid: "919800000001@c.us", keyId: "3EB0ABC123" };

  test("uses _serialized when the key has it", () => {
    expect(serializedMessageId({ ...parts, serialized: "false_919800000001@c.us_3EB0ABC123", text: "[object Object]" })).toBe(
      "false_919800000001@c.us_3EB0ABC123",
    );
  });

  test("falls back to the key's toString()", () => {
    expect(serializedMessageId({ ...parts, serialized: undefined, text: "false_1234567890@lid_AC55" })).toBe("false_1234567890@lid_AC55");
  });

  test("builds it from the key's parts when neither is there (WhatsApp Web 2.3000.105)", () => {
    expect(serializedMessageId({ ...parts, serialized: undefined, text: "[object Object]" })).toBe("false_919800000001@c.us_3EB0ABC123");
    expect(serializedMessageId({ ...parts, fromMe: true, serialized: undefined, text: null })).toBe("true_919800000001@c.us_3EB0ABC123");
  });

  test("null when the parts are missing", () => {
    expect(serializedMessageId({ ...parts, keyId: undefined, serialized: undefined, text: "[object Object]" })).toBeNull();
    expect(serializedMessageId({ ...parts, remoteJid: null, serialized: undefined, text: null })).toBeNull();
    expect(serializedMessageId({ ...parts, fromMe: undefined, serialized: undefined, text: null })).toBeNull();
  });
});

describe("jidToPhone", () => {
  test("a phone jid is its number", () => {
    expect(jidToPhone("919876543210@c.us")).toBe("+919876543210");
    expect(jidToPhone("14155550100@s.whatsapp.net")).toBe("+14155550100");
    expect(jidToPhone("14155550100:12@s.whatsapp.net")).toBe("+14155550100");
  });
  test("lid, group and broadcast ids have no number", () => {
    for (const jid of ["123456789012345@lid", "120363000000000000@g.us", "status@broadcast", "1234@newsletter", null, ""]) {
      expect(jidToPhone(jid)).toBeNull();
    }
  });
  test("non-personal chats", () => {
    expect(isNonPersonalJid("120363000000000000@g.us")).toBe(true);
    expect(isNonPersonalJid("status@broadcast")).toBe(true);
    expect(isNonPersonalJid("1234@newsletter")).toBe(true);
    expect(isNonPersonalJid("919876543210@c.us")).toBe(false);
    expect(isNonPersonalJid("123456789012345@lid")).toBe(false);
  });
});

describe("message types", () => {
  test("keeps what a person sends, skips the rest", () => {
    for (const type of ["chat", "image", "video", "ptt", "audio", "document", "sticker", "location", "vcard"]) {
      expect(isKeptMessageType(type)).toBe(true);
    }
    for (const type of ["e2e_notification", "notification_template", "gp2", "protocol", "revoked", "call_log", "ciphertext", "", null]) {
      expect(isKeptMessageType(type)).toBe(false);
    }
  });
});

describe("storeMessage", () => {
  const base: StoreMessageFields = {
    id: "false_919876543210@c.us_KEY",
    fromMe: false,
    chatJid: "919876543210@c.us",
    lidPhone: null,
    t: 1_790_000_000,
    type: "chat",
    body: "Hi, call me tomorrow",
    caption: undefined,
    chatName: "Rahul",
  };
  test("a lead's text", () => {
    expect(storeMessage(base)).toEqual({
      providerMessageId: "false_919876543210@c.us_KEY",
      chatPhone: "+919876543210",
      chatJid: "919876543210@c.us",
      chatName: "Rahul",
      direction: "inbound",
      text: "Hi, call me tomorrow",
      sentAt: 1_790_000_000_000,
      kind: null,
    });
  });
  test("media keeps its caption and type; outbound is fromMe", () => {
    const message = storeMessage({ ...base, fromMe: true, type: "image", body: "/9j/4AAQ…", caption: "the brochure" });
    expect(message?.direction).toBe("outbound");
    expect(message?.text).toBe("the brochure");
    expect(message?.kind).toBe("image");
    expect(storeMessage({ ...base, type: "ptt", body: "base64…", caption: undefined })?.text).toBe("");
  });
  test("a lid chat takes the number WhatsApp maps it to, if any", () => {
    expect(storeMessage({ ...base, chatJid: "123456789012345@lid", lidPhone: "919876543210" })?.chatPhone).toBe("+919876543210");
    expect(storeMessage({ ...base, chatJid: "123456789012345@lid" })?.chatPhone).toBeNull();
  });
  test("groups, broadcasts and notifications are dropped", () => {
    expect(storeMessage({ ...base, chatJid: "120363000000000000@g.us" })).toBeNull();
    expect(storeMessage({ ...base, chatJid: "status@broadcast" })).toBeNull();
    expect(storeMessage({ ...base, type: "e2e_notification" })).toBeNull();
    expect(storeMessage({ ...base, id: null })).toBeNull();
  });
});

describe("parsePrePlainText", () => {
  const now = new Date(2026, 9, 27, 18, 0).getTime();
  test("day-first 24-hour", () => {
    const parsed = parsePrePlainText("[10:42, 27/10/2026] Rahul Sharma: ", now);
    expect(parsed.sender).toBe("Rahul Sharma");
    expect(parsed.sentAt).toBe(new Date(2026, 9, 27, 10, 42).getTime());
  });
  test("month-first 12-hour", () => {
    expect(parsePrePlainText("[3:05 PM, 10/27/2026] +91 98765 43210: ", now).sentAt).toBe(new Date(2026, 9, 27, 15, 5).getTime());
    expect(parsePrePlainText("[12:10 am, 10/27/2026] A: ", now).sentAt).toBe(new Date(2026, 9, 27, 0, 10).getTime());
  });
  test("an ambiguous date is read as the one not in the future, closest to now", () => {
    // 10/09 is 10 Sep or 9 Oct; both past — 9 Oct is closer.
    expect(parsePrePlainText("[09:00, 10/09/2026] A: ", now).sentAt).toBe(new Date(2026, 9, 9, 9, 0).getTime());
    // 02/11 is 2 Nov (future) or 11 Feb — only 11 Feb is possible.
    expect(parsePrePlainText("[09:00, 02/11/2026] A: ", now).sentAt).toBe(new Date(2026, 1, 11, 9, 0).getTime());
  });
  test("something else reads as nothing", () => {
    expect(parsePrePlainText("hello", now)).toEqual({ sender: null, sentAt: null });
    expect(parsePrePlainText(null, now)).toEqual({ sender: null, sentAt: null });
    expect(parsePrePlainText("[yesterday] A: ", now)).toEqual({ sender: "A", sentAt: null });
  });
});

describe("mergeInbound", () => {
  const message = (id: string, text = "x"): StationInboundMessage => ({
    providerMessageId: id,
    chatPhone: "+919876543210",
    chatJid: "919876543210@c.us",
    chatName: null,
    direction: "inbound",
    text,
    sentAt: 1,
  });
  test("adds new messages and skips ones seen, by key id", () => {
    const first = mergeInbound({ messages: [], seen: [] }, [message("false_919876543210@c.us_A"), message("false_919876543210@c.us_B")]);
    expect(first.added).toBe(2);
    // The same message read from the DOM under a lid chat id is still a repeat.
    const second = mergeInbound(first, [message("false_123@lid_A"), message("false_919876543210@c.us_C")]);
    expect(second.added).toBe(1);
    expect(second.messages.map((m) => m.providerMessageId)).toEqual([
      "false_919876543210@c.us_A",
      "false_919876543210@c.us_B",
      "false_919876543210@c.us_C",
    ]);
    // Taken (buffer emptied) — still remembered as seen.
    expect(mergeInbound({ messages: [], seen: second.seen }, [message("false_919876543210@c.us_B")]).added).toBe(0);
  });
  test("bounds the buffer and the seen list, dropping the oldest", () => {
    const incoming = Array.from({ length: 8 }, (_, i) => message(`false_1234567@c.us_K${i}`));
    const merged = mergeInbound({ messages: [], seen: [] }, incoming, { buffer: 5, seen: 6 });
    expect(merged.messages.map((m) => m.providerMessageId)).toEqual(incoming.slice(3).map((m) => m.providerMessageId));
    expect(merged.seen).toEqual(["K2", "K3", "K4", "K5", "K6", "K7"]);
  });
});
