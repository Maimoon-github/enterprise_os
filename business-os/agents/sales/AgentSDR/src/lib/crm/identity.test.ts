import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { identityExceptionReplayInput } from "./identity";
import type { crmIdentityExceptions } from "./schema";

type IdentityException = typeof crmIdentityExceptions.$inferSelect;

function exception(overrides: Partial<IdentityException>): IdentityException {
  const now = new Date("2026-09-02T12:00:00.000Z");
  return {
    id: "00000000-0000-4000-8000-000000000001",
    organizationId: "00000000-0000-0000-0000-00000000000a",
    channel: "linkedin",
    accountRef: "account-1",
    sourceEventKey: "event-1",
    identityValue: "provider-1",
    reason: "Needs a Person",
    payload: {},
    status: "open",
    resolvedPersonId: null,
    resolvedAt: null,
    createdAt: now,
    updatedAt: now,
    ...overrides,
  };
}

describe("CRM identity exception replay", () => {
  it("rebuilds a LinkedIn inbound event for the selected Person", () => {
    const input = identityExceptionReplayInput(exception({
      payload: {
        providerId: "provider-1",
        chatId: "chat-1",
        linkedinMessageId: "message-1",
        messageText: "Interested",
        sentAt: "2026-09-02T11:30:00.000Z",
      },
    }), "00000000-0000-4000-8000-000000000002");

    assert.deepEqual({
      personId: input.personId,
      channel: input.channel,
      accountRef: input.accountRef,
      providerThreadId: input.providerThreadId,
      providerContactId: input.providerContactId,
      providerMessageId: input.providerMessageId,
      idempotencyKey: input.idempotencyKey,
      bodyText: input.bodyText,
      actorRef: input.actorRef,
    }, {
      personId: "00000000-0000-4000-8000-000000000002",
      channel: "linkedin",
      accountRef: "account-1",
      providerThreadId: "chat-1",
      providerContactId: "provider-1",
      providerMessageId: "message-1",
      idempotencyKey: "event-1",
      bodyText: "Interested",
      actorRef: "identity-review",
    });
    assert.equal(input.sentAt.toISOString(), "2026-09-02T11:30:00.000Z");
  });

  it("rebuilds Gmail and provider-neutral stored email payloads", () => {
    const gmail = identityExceptionReplayInput(exception({
      channel: "email",
      identityValue: "person@example.com",
      payload: {
        gmailMessageId: "gmail-1",
        threadId: "thread-1",
        messageId: "rfc-1",
        subject: "Re: Hello",
        bodyText: "Yes, let's talk.",
        internalDate: "2026-09-02T10:00:00.000Z",
      },
    }), "00000000-0000-4000-8000-000000000002");
    assert.equal(gmail.providerThreadId, "thread-1");
    assert.equal(gmail.providerMessageId, "rfc-1");
    assert.equal(gmail.bodyText, "Yes, let's talk.");

    const providerEvent = identityExceptionReplayInput(exception({
      channel: "email",
      identityValue: "person@example.com",
      payload: { vendorLeadId: "lead-1", messageId: "message-2", replyBody: "Not now" },
    }), "00000000-0000-4000-8000-000000000002");
    assert.equal(providerEvent.providerContactId, "lead-1");
    assert.equal(providerEvent.providerMessageId, "message-2");
    assert.equal(providerEvent.bodyText, "Not now");
  });

  it("refuses to close an exception whose stored payload cannot be replayed", () => {
    assert.throws(
      () => identityExceptionReplayInput(exception({ payload: {} }), "00000000-0000-4000-8000-000000000002"),
      /LinkedIn message text is missing/,
    );
  });
});
