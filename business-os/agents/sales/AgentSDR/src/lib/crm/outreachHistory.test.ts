import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  emailOutreachRowToMessageInput,
  linkedinOutreachRowToMessageInput,
  type EmailOutreachRow,
  type LinkedinOutreachRow,
} from "./outreachHistory";

function emailRow(overrides: Partial<EmailOutreachRow> = {}): EmailOutreachRow {
  return {
    id: "email-1",
    subject: "Quick question",
    body: "Hi there, wanted to reach out.",
    messageId: "<rfc-1@example.test>",
    sentAt: new Date("2026-09-01T09:00:00.000Z"),
    stepNumber: 1,
    campaignId: "campaign-1",
    ...overrides,
  };
}

function linkedinRow(overrides: Partial<LinkedinOutreachRow> = {}): LinkedinOutreachRow {
  return {
    id: "message-1",
    type: "INVITATION",
    text: "Would love to connect.",
    linkedinMessageId: "li-1",
    createdAt: new Date("2026-09-01T09:00:00.000Z"),
    duplicateOfMessageId: null,
    campaignId: "campaign-1",
    ...overrides,
  };
}

describe("emailOutreachRowToMessageInput", () => {
  it("maps a sent plain-text email to an outbound message", () => {
    const input = emailOutreachRowToMessageInput(emailRow());
    assert.ok(input);
    assert.equal(input.direction, "outbound");
    assert.equal(input.idempotencyKey, "outreach-email:email-1");
    assert.equal(input.providerMessageId, "<rfc-1@example.test>");
    assert.equal(input.subject, "Quick question");
    assert.equal(input.bodyText, "Hi there, wanted to reach out.");
    assert.equal(input.bodyHtml, null);
    assert.deepEqual(input.raw, {
      source: "outreach_emails",
      id: "email-1",
      step: 1,
      campaignId: "campaign-1",
    });
    assert.equal(input.sentAt.toISOString(), "2026-09-01T09:00:00.000Z");
  });

  it("converts an HTML body to plain text and keeps the original HTML", () => {
    const html = "<p>Hi <b>there</b>,</p><p>wanted to reach out.</p>";
    const input = emailOutreachRowToMessageInput(emailRow({ body: html }));
    assert.ok(input);
    assert.equal(input.bodyText, "Hi there,\nwanted to reach out.");
    assert.equal(input.bodyHtml, html);
  });

  it("skips a row whose body is empty after trimming", () => {
    assert.equal(emailOutreachRowToMessageInput(emailRow({ body: "   " })), null);
    assert.equal(emailOutreachRowToMessageInput(emailRow({ body: null })), null);
    assert.equal(emailOutreachRowToMessageInput(emailRow({ body: "<p></p>" })), null);
  });

  it("skips a row with no sentAt (not actually sent)", () => {
    assert.equal(emailOutreachRowToMessageInput(emailRow({ sentAt: null })), null);
  });
});

describe("linkedinOutreachRowToMessageInput", () => {
  it("maps an outbound Message row and always sets subject to null", () => {
    const input = linkedinOutreachRowToMessageInput(linkedinRow());
    assert.ok(input);
    assert.equal(input.direction, "outbound");
    assert.equal(input.idempotencyKey, "linkedin-outreach:message-1");
    assert.equal(input.providerMessageId, "li-1");
    assert.equal(input.subject, null);
    assert.equal(input.bodyText, "Would love to connect.");
    assert.deepEqual(input.raw, {
      source: "Message",
      id: "message-1",
      type: "INVITATION",
      campaignId: "campaign-1",
    });
    assert.equal(input.sentAt.toISOString(), "2026-09-01T09:00:00.000Z");
  });

  it("excludes RECEIVED rows (inbound; the CRM already gets those from the webhook)", () => {
    assert.equal(linkedinOutreachRowToMessageInput(linkedinRow({ type: "RECEIVED" })), null);
  });

  it("excludes rows marked as a duplicate of another message", () => {
    assert.equal(
      linkedinOutreachRowToMessageInput(linkedinRow({ duplicateOfMessageId: "message-0" })),
      null,
    );
  });

  it("skips a row whose text is empty after trimming", () => {
    assert.equal(linkedinOutreachRowToMessageInput(linkedinRow({ text: "   " })), null);
    assert.equal(linkedinOutreachRowToMessageInput(linkedinRow({ text: null })), null);
  });

  it("accepts every non-RECEIVED type, including CUSTOM_SENT", () => {
    for (const type of ["ACCEPTANCE", "FOLLOW_UP_1", "FOLLOW_UP_2", "FOLLOW_UP_3", "CUSTOM_SENT"] as const) {
      assert.ok(linkedinOutreachRowToMessageInput(linkedinRow({ type })));
    }
  });
});
