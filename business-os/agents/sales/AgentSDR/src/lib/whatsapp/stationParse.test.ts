import { describe, expect, test } from "bun:test";
import {
  isNonPersonJid,
  jidPhone,
  jobOutcomeForResult,
  jobOutcomeWhenStale,
  parseIncomingCallRequest,
  parseInboundRequest,
  parseMessageClaim,
  parseMessageResult,
  parseWhatsappMessageId,
  pickStationEcho,
  RETRY_MARK,
  stationAccountRef,
  stationAttachments,
  stationChatId,
  stationChatKey,
  stationMessageKey,
  StationReportError,
  UNCERTAIN_DELIVERY_ERROR,
} from "./stationParse";

const STATION = "6f1c2c1e-1d2b-4c51-9a55-3a8d0c7b1e01";

describe("ids", () => {
  test("account and chat ids", () => {
    expect(stationAccountRef(STATION)).toBe(`station:${STATION}`);
    expect(stationChatId("+91 98765-43210")).toBe("919876543210@s.whatsapp.net");
  });

  test("jidPhone reads user jids only", () => {
    expect(jidPhone("919876543210@c.us")).toBe("+919876543210");
    expect(jidPhone("919876543210@s.whatsapp.net")).toBe("+919876543210");
    expect(jidPhone("919876543210:12@s.whatsapp.net")).toBe("+919876543210");
    expect(jidPhone("123456789012345@lid")).toBeNull();
    expect(jidPhone("1203630@g.us")).toBeNull();
    expect(jidPhone(null)).toBeNull();
  });

  test("non-person chats", () => {
    expect(isNonPersonJid("120363041234567890@g.us")).toBe(true);
    expect(isNonPersonJid("status@broadcast")).toBe(true);
    expect(isNonPersonJid("1203@newsletter")).toBe(true);
    expect(isNonPersonJid("919876543210@c.us")).toBe(false);
    expect(isNonPersonJid("12345@lid")).toBe(false);
  });

  test("message ids: serialized, data-id, bare", () => {
    expect(parseWhatsappMessageId("true_919876543210@c.us_3EB0A1B2C3D4")).toEqual({ fromMe: true, jid: "919876543210@c.us", keyId: "3EB0A1B2C3D4" });
    expect(parseWhatsappMessageId("false_12345@lid_ABCDEF123456")).toEqual({ fromMe: false, jid: "12345@lid", keyId: "ABCDEF123456" });
    expect(parseWhatsappMessageId("false_1203@g.us_ABCD1234_9198@c.us")?.keyId).toBe("ABCD1234");
    expect(parseWhatsappMessageId("3EB0A1B2C3D4")).toEqual({ fromMe: null, jid: null, keyId: "3EB0A1B2C3D4" });
    expect(parseWhatsappMessageId("  ")).toBeNull();
    expect(parseWhatsappMessageId("not an id")).toBeNull();
  });

  test("the message key is the key id per station, whichever form was read", () => {
    const serialized = stationMessageKey(STATION, "true_919876543210@c.us_3EB0A1");
    expect(serialized).toBe(`station:${STATION}:3EB0A1`);
    expect(stationMessageKey(STATION, "true_12345@lid_3EB0A1")).toBe(serialized);
    expect(stationMessageKey(STATION, "3EB0A1")).toBe(serialized);
    expect(stationMessageKey("other", "3EB0A1")).not.toBe(serialized);
  });

  test("chat key: by number when known, else the jid", () => {
    expect(stationChatKey({ chatPhone: "+919876543210", chatJid: "555@lid" })).toEqual({ unipileChatId: "919876543210@s.whatsapp.net", phone: "+919876543210" });
    expect(stationChatKey({ chatPhone: null, chatJid: "919876543210@c.us" })).toEqual({ unipileChatId: "919876543210@s.whatsapp.net", phone: "+919876543210" });
    expect(stationChatKey({ chatPhone: null, chatJid: "555@lid" })).toEqual({ unipileChatId: "555@lid", phone: null });
  });

  test("attachments", () => {
    expect(stationAttachments(null)).toEqual([]);
    expect(stationAttachments("chat")).toEqual([]);
    expect(stationAttachments("image")[0]?.type).toBe("img");
    expect(stationAttachments("ptt")[0]?.type).toBe("audio");
    expect(stationAttachments("document")[0]?.type).toBe("file");
  });
});

describe("echo matching", () => {
  const at = (s: number) => new Date(Date.UTC(2026, 9, 27, 10, 0, s));
  test("oldest with the same text wins", () => {
    const candidates = [
      { id: "b", body: "Hi there", sentAt: at(20) },
      { id: "a", body: "Hi there\r\n", sentAt: at(10) },
      { id: "c", body: "Other", sentAt: at(5) },
    ];
    expect(pickStationEcho(candidates, " Hi there")?.id).toBe("a");
    expect(pickStationEcho(candidates, "nope")).toBeNull();
  });
});

describe("message job transitions", () => {
  const claimed = { status: "claimed" as const, error: null };
  test("sent is taken from a claim, or a requeued job (it went out)", () => {
    expect(jobOutcomeForResult(claimed, { ok: true, providerMessageId: null, sentAt: 1 })).toEqual({ action: "sent" });
    expect(jobOutcomeForResult({ status: "queued", error: `${RETRY_MARK}x` }, { ok: true, providerMessageId: null, sentAt: 1 })).toEqual({ action: "sent" });
  });
  test("settled jobs ignore reports", () => {
    expect(jobOutcomeForResult({ status: "sent", error: null }, { ok: false, error: "x" })).toEqual({ action: "ignore" });
    expect(jobOutcomeForResult({ status: "failed", error: "x" }, { ok: true, providerMessageId: null, sentAt: 1 })).toEqual({ action: "ignore" });
  });
  test("a failure counts only from the claim", () => {
    expect(jobOutcomeForResult({ status: "queued", error: null }, { ok: false, error: "x" })).toEqual({ action: "ignore" });
    expect(jobOutcomeForResult(claimed, { ok: false, error: "not on WhatsApp" })).toEqual({ action: "fail", error: "not on WhatsApp" });
  });
  test("a retryable failure requeues once, then fails", () => {
    const first = jobOutcomeForResult(claimed, { ok: false, error: "call active", retryable: true });
    expect(first).toEqual({ action: "requeue", error: `${RETRY_MARK}call active` });
    const second = jobOutcomeForResult({ status: "claimed", error: (first as { error: string }).error }, { ok: false, error: "call active", retryable: true });
    expect(second).toEqual({ action: "fail", error: "call active" });
  });
  test("a send that may have gone out fails as uncertain, never requeued", () => {
    const text = "The message box emptied but the sent message did not show within 10 s — it may have been sent";
    expect(jobOutcomeForResult(claimed, { ok: false, error: "x", retryable: true, uncertain: true })).toEqual({ action: "fail", error: "x", uncertain: true });
    // Workers before the flag said so only in the text.
    expect(jobOutcomeForResult(claimed, { ok: false, error: text })).toEqual({ action: "fail", error: text, uncertain: true });
  });
  test("a stale claim is never requeued: it fails as uncertain, keeping the message", () => {
    expect(jobOutcomeWhenStale(claimed)).toEqual({ action: "fail", error: UNCERTAIN_DELIVERY_ERROR, uncertain: true });
    expect(jobOutcomeWhenStale({ status: "claimed", error: `${RETRY_MARK}x` })).toEqual({ action: "fail", error: UNCERTAIN_DELIVERY_ERROR, uncertain: true });
    expect(jobOutcomeWhenStale({ status: "queued", error: null })).toEqual({ action: "ignore" });
  });
  test("a late sent report settles an uncertain job; nothing else revives a failed one", () => {
    const uncertain = { status: "failed" as const, error: UNCERTAIN_DELIVERY_ERROR };
    expect(jobOutcomeForResult(uncertain, { ok: true, providerMessageId: null, sentAt: 1 })).toEqual({ action: "sent" });
    expect(jobOutcomeForResult(uncertain, { ok: false, error: "x", retryable: true })).toEqual({ action: "ignore" });
  });
});

describe("incoming call report", () => {
  test("keeps what it needs, trims, and defaults the flags", () => {
    expect(parseIncomingCallRequest({ workerId: " w1 ", call: { waCallId: " ABC ", phone: "+919800000001", at: 5, isVideo: true } })).toEqual({
      workerId: "w1",
      call: { waCallId: "ABC", phone: "+919800000001", callerName: null, isVideo: true, isGroup: false, at: 5 },
    });
  });
  test("a hidden number is null, not refused", () => {
    expect(parseIncomingCallRequest({ workerId: "w1", call: { waCallId: "A", phone: "", at: 1 } }).call.phone).toBeNull();
  });
  test("refuses a report without the worker, the call id or the time", () => {
    expect(() => parseIncomingCallRequest({ call: { waCallId: "A", at: 1 } })).toThrow(StationReportError);
    expect(() => parseIncomingCallRequest({ workerId: "w1", call: { at: 1 } })).toThrow(StationReportError);
    expect(() => parseIncomingCallRequest({ workerId: "w1", call: { waCallId: "A" } })).toThrow(StationReportError);
  });
});

describe("worker reports", () => {
  test("claim", () => {
    expect(parseMessageClaim({ workerId: " w1 ", stations: [STATION] })).toEqual({ workerId: "w1", stations: [STATION] });
    expect(() => parseMessageClaim({ workerId: "w1", stations: ["x"] })).toThrow(StationReportError);
    expect(() => parseMessageClaim({ stations: [] })).toThrow(StationReportError);
  });

  test("result", () => {
    expect(parseMessageResult({ ok: true, providerMessageId: " true_1@c.us_AB12 ", sentAt: 5 })).toEqual({ ok: true, providerMessageId: "true_1@c.us_AB12", sentAt: 5 });
    expect(parseMessageResult({ ok: false, error: "x", retryable: true })).toEqual({ ok: false, error: "x", retryable: true, uncertain: false });
    expect(parseMessageResult({ ok: false, error: "x", uncertain: true })).toEqual({ ok: false, error: "x", retryable: false, uncertain: true });
    expect(parseMessageResult({ ok: false })).toEqual({ ok: false, error: "The call worker could not send the message", retryable: false, uncertain: false });
    expect(() => parseMessageResult({})).toThrow(StationReportError);
  });

  test("inbound drops what cannot be stored and clamps future times", () => {
    const now = 1_800_000_000_000;
    const parsed = parseInboundRequest({
      source: "store",
      messages: [
        { providerMessageId: "false_919876543210@c.us_AB12CD", chatPhone: "+919876543210", chatJid: "919876543210@c.us", chatName: "Asha", direction: "inbound", text: "Yes, call me", sentAt: now + 60_000 },
        { providerMessageId: "false_1203@g.us_AB12CD_9198@c.us", chatPhone: null, chatJid: "1203@g.us", chatName: null, direction: "inbound", text: "group", sentAt: now },
        { providerMessageId: "", chatJid: "919876543210@c.us", direction: "inbound", text: "no id", sentAt: now },
        { providerMessageId: "AB12CE", chatJid: "55@lid", direction: "sideways", text: "bad direction", sentAt: now },
        { providerMessageId: "AB12CF", chatPhone: "not a phone", chatJid: "55@lid", direction: "outbound", sentAt: now - 5, kind: "image" },
      ],
    }, now);
    expect(parsed.source).toBe("store");
    expect(parsed.messages).toHaveLength(2);
    expect(parsed.messages[0]).toMatchObject({ chatPhone: "+919876543210", sentAt: now, text: "Yes, call me", kind: null });
    expect(parsed.messages[1]).toMatchObject({ chatPhone: null, chatName: null, text: "", kind: "image", sentAt: now - 5 });
    expect(parseInboundRequest({ source: "weird", messages: [] }).source).toBe("none");
    expect(() => parseInboundRequest({ messages: "x" })).toThrow(StationReportError);
  });
});
