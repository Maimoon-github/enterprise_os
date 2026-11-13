import { describe, expect, test } from "bun:test";
import { buildThreadHeaders, isRfcMessageId, resolveExtraRecipients, sentRecipients } from "./send";
import { messageParticipants } from "./participants";

describe("email reply threading", () => {
  test("only angle-bracketed ids count as RFC Message-IDs", () => {
    expect(isRfcMessageId("<a@b.com>")).toBe(true);
    expect(isRfcMessageId("18c3f0a1b2c3d4e5")).toBe(false);
    expect(isRfcMessageId(null)).toBe(false);
  });

  test("References is the conversation chain ending with the message answered", () => {
    const headers = buildThreadHeaders([
      { raw: { messageId: "<1@x.com>" }, providerMessageId: "g1" },
      { raw: { messageId: null }, providerMessageId: "g2" },
      { raw: { messageId: "<3@x.com>" }, providerMessageId: "g3" },
    ]);
    expect(headers.inReplyTo).toBe("<3@x.com>");
    expect(headers.references).toEqual(["<1@x.com>", "<3@x.com>"]);
  });

  test("a bare Gmail id is never In-Reply-To", () => {
    expect(buildThreadHeaders([{ raw: null, providerMessageId: "18c3f0a1b2c3d4e5" }]).inReplyTo).toBeNull();
    expect(buildThreadHeaders([{ raw: null, providerMessageId: "<ok@x.com>" }]).inReplyTo).toBe("<ok@x.com>");
    expect(buildThreadHeaders([])).toEqual({ inReplyTo: null, references: [] });
  });

  test("References keeps the last 20", () => {
    const messages = Array.from({ length: 30 }, (_, i) => ({ raw: { messageId: `<${i}@x.com>` }, providerMessageId: null }));
    const { references } = buildThreadHeaders(messages);
    expect(references).toHaveLength(20);
    expect(references.at(-1)).toBe("<29@x.com>");
  });
});

describe("extra recipients", () => {
  test("drops the lead and our mailbox, and bcc never repeats a cc", () => {
    const out = resolveExtraRecipients(
      { ccEmails: ["Lead@x.com", "boss@x.com", "me@us.com"], bccEmails: ["boss@x.com", "audit@x.com"] },
      { recipient: "lead@x.com", mailbox: "me@us.com" },
    );
    expect(out).toEqual({ cc: ["boss@x.com"], bcc: ["audit@x.com"] });
  });

  test("sentRecipients records to/cc/bcc as EmailAddress[]", () => {
    expect(sentRecipients({ recipientEmail: "lead@x.com", ccEmails: ["b@x.com"], bccEmails: [] })).toEqual({
      to: [{ email: "lead@x.com", name: null }],
      cc: [{ email: "b@x.com", name: null }],
      bcc: [],
    });
  });
});

describe("messageParticipants", () => {
  test("inbound reads the parsed message, outbound uses the mailbox as sender", () => {
    expect(messageParticipants({
      channel: "email", direction: "inbound", accountRef: "me@us.com",
      raw: { fromEmail: "Lead@x.com", to: [{ email: "me@us.com", name: null }], cc: [{ email: "boss@x.com", name: null }] },
    })).toEqual({ from: "lead@x.com", to: ["me@us.com"], cc: ["boss@x.com"] });
    expect(messageParticipants({
      channel: "email", direction: "outbound", accountRef: "me@us.com",
      raw: { to: [{ email: "lead@x.com", name: null }], cc: [], bcc: [{ email: "secret@x.com", name: null }] },
    })).toEqual({ from: "me@us.com", to: ["lead@x.com"], cc: [] });
    expect(messageParticipants({ channel: "linkedin", direction: "inbound", accountRef: "a", raw: {} })).toBeUndefined();
  });
});
