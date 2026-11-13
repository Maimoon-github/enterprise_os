import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  InboxSendError,
  sendFromLinkedinInbox,
  type InboxCrmConversation,
  type InboxSendConnection,
  type InboxSendDependencies,
  type InboxSentMessage,
} from "./sendFromInbox";

const connection: InboxSendConnection = {
  id: "connection-1",
  chatId: "chat-1",
  leadId: "lead-1",
  linkedinUrl: "person",
  linkedinAccountId: "account-1",
};
const crmConversation: InboxCrmConversation = {
  id: "conversation-1",
  recordId: "record-1",
  personId: "person-1",
};
const sentMessage: InboxSentMessage = {
  id: "message-1",
  type: "CUSTOM_SENT",
  text: "Hello",
  seen: true,
  createdAt: "2026-09-03T00:00:00.000Z",
};

function dependencies(overrides: Partial<InboxSendDependencies> = {}) {
  const calls = { crm: 0, linkedin: 0, saved: 0 };
  const value: InboxSendDependencies = {
    findConnection: async () => connection,
    findNativePersonId: async () => "person-1",
    findCrmConversation: async () => null,
    isPersonDoNotContact: async () => false,
    sendThroughCrm: async () => { calls.crm += 1; return sentMessage; },
    sendThroughLinkedin: async () => { calls.linkedin += 1; return "provider-message-1"; },
    saveNativeMessage: async () => { calls.saved += 1; return sentMessage; },
    ...overrides,
  };
  return { calls, value };
}

describe("LinkedIn inbox manual sending", () => {
  test("routes an existing CRM conversation through CRM without blocking it", async () => {
    const setup = dependencies({ findCrmConversation: async () => crmConversation });
    const result = await sendFromLinkedinInbox(
      { connectionId: connection.id, text: "  Hello  ", idempotencyKey: "request-1" },
      setup.value,
    );

    assert.deepEqual(result, sentMessage);
    assert.deepEqual(setup.calls, { crm: 1, linkedin: 0, saved: 0 });
  });

  test("routes a non-CRM conversation through the native LinkedIn sender", async () => {
    const setup = dependencies();
    const result = await sendFromLinkedinInbox(
      { connectionId: connection.id, text: "Hello", idempotencyKey: "request-2" },
      setup.value,
    );

    assert.deepEqual(result, sentMessage);
    assert.deepEqual(setup.calls, { crm: 0, linkedin: 1, saved: 1 });
  });

  test("keeps global Do Not Contact as the only ownership-independent send restriction", async () => {
    const setup = dependencies({
      findNativePersonId: async () => null,
      findCrmConversation: async () => crmConversation,
      isPersonDoNotContact: async () => true,
    });

    await assert.rejects(
      sendFromLinkedinInbox(
        { connectionId: connection.id, text: "Hello", idempotencyKey: "request-3" },
        setup.value,
      ),
      (error: unknown) => error instanceof InboxSendError && error.status === 409,
    );
    assert.deepEqual(setup.calls, { crm: 0, linkedin: 0, saved: 0 });
  });
});
