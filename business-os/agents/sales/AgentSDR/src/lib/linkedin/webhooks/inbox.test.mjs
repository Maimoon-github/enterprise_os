import { describe, expect, test } from "bun:test";
import {
  internalWebhookReplayId,
  linkedinWebhookEventKey,
  markInternalWebhookReplay,
  stableWebhookJson,
  webhookRetryDelayMs,
} from "./inbox.ts";

describe("LinkedIn webhook inbox", () => {
  test("scopes message delivery identity by account and provider message id", () => {
    expect(linkedinWebhookEventKey({
      event: "message_received",
      account_type: "LINKEDIN",
      account_id: "account-1",
      message_id: "message-1",
      message: "hello",
    })).toBe("linkedin:LINKEDIN:message_received:v1:account-1:message-1");

    expect(linkedinWebhookEventKey({
      event: "message_received",
      account_type: "LINKEDIN",
      account_id: "account-2",
      message_id: "message-1",
    })).not.toBe("linkedin:LINKEDIN:message_received:v1:account-1:message-1");
  });

  test("does not pretend new_relation has a provider event id", () => {
    expect(linkedinWebhookEventKey({
      event: "new_relation",
      account_type: "LINKEDIN",
      account_id: "account-1",
      user_provider_id: "person-1",
      timestamp: "2026-08-27T12:00:00.000Z",
    })).toBe("linkedin:LINKEDIN:new_relation:v1:account-1:person-1:2026-08-27T12:00:00.000Z");
  });

  test("canonical payload fallback is stable across object key order", () => {
    const left = { event: "new_relation", account_id: "a", nested: { z: 1, a: [2, 3] } };
    const right = { nested: { a: [2, 3], z: 1 }, account_id: "a", event: "new_relation" };
    expect(stableWebhookJson(left)).toBe(stableWebhookJson(right));
    expect(linkedinWebhookEventKey(left)).toBe(linkedinWebhookEventKey(right));
  });

  test("fallback distinguishes otherwise identical messages with different payload timestamps", () => {
    const base = { event: "message_received", account_id: "a", message: "same" };
    expect(linkedinWebhookEventKey({ ...base, timestamp: "2026-08-27T12:00:00Z" }))
      .not.toBe(linkedinWebhookEventKey({ ...base, timestamp: "2026-08-27T12:00:01Z" }));
  });

  test("retry backoff is bounded", () => {
    expect(webhookRetryDelayMs(1)).toBe(5_000);
    expect(webhookRetryDelayMs(2)).toBe(10_000);
    expect(webhookRetryDelayMs(20)).toBe(15 * 60_000);
  });

  test("internal replay marker cannot be forged as a request property", () => {
    const request = { internalWebhookEventId: "forged" };
    expect(internalWebhookReplayId(request)).toBeNull();
    markInternalWebhookReplay(request, "event-1");
    expect(internalWebhookReplayId(request)).toBe("event-1");
  });
});
