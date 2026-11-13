import { describe, expect, test } from "bun:test";
import { gmailInboundEventKey } from "./inboundIdentity.ts";

describe("Gmail inbound identity", () => {
  test("is stable across mailbox casing and does not depend on optional RFC Message-Id", () => {
    expect(gmailInboundEventKey(" Sales@Example.com ", "gmail-123"))
      .toBe("gmail:sales@example.com:gmail-123");
  });

  test("scopes identical Gmail IDs to the receiving mailbox", () => {
    expect(gmailInboundEventKey("a@example.com", "same"))
      .not.toBe(gmailInboundEventKey("b@example.com", "same"));
  });

  test("rejects incomplete identities", () => {
    expect(() => gmailInboundEventKey("a@example.com", " ")).toThrow();
  });
});
