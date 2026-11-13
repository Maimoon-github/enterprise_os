import { beforeAll, describe, expect, test } from "bun:test";
import {
  buildLegacyUnsubscribeToken,
  buildUnsubscribeToken,
  verifyUnsubscribeToken,
} from "./unsubscribeToken";

const ORG = "00000000-0000-0000-0000-00000000000a";

beforeAll(() => {
  process.env.UNSUBSCRIBE_SECRET = "test-secret";
});

describe("unsubscribe tokens", () => {
  test("a v2 token carries its organization and the normalized email", () => {
    const token = buildUnsubscribeToken("  Lead.One@Example.com ", ORG);
    expect(verifyUnsubscribeToken(token)).toEqual({ ok: true, email: "lead.one@example.com", organizationId: ORG });
  });

  test("a legacy token still verifies and names no organization", () => {
    const token = buildLegacyUnsubscribeToken("lead@example.com");
    expect(verifyUnsubscribeToken(token)).toEqual({ ok: true, email: "lead@example.com", organizationId: null });
  });

  test("tampering with the organization or email is rejected", () => {
    const decoded = Buffer.from(buildUnsubscribeToken("lead@example.com", ORG), "base64url").toString();
    const otherOrg = decoded.replace(ORG, "00000000-0000-0000-0000-00000000000b");
    expect(verifyUnsubscribeToken(Buffer.from(otherOrg).toString("base64url")).ok).toBe(false);
    const otherEmail = decoded.replace("lead@", "evil@");
    expect(verifyUnsubscribeToken(Buffer.from(otherEmail).toString("base64url")).ok).toBe(false);
    expect(verifyUnsubscribeToken("not-a-token").ok).toBe(false);
  });

  test("a legacy signature cannot be replayed as a v2 token", () => {
    const sig = Buffer.from(buildLegacyUnsubscribeToken("lead@example.com"), "base64url").toString().split(".").pop();
    const forged = Buffer.from(`v2.${ORG}.lead@example.com.${sig}`).toString("base64url");
    expect(verifyUnsubscribeToken(forged).ok).toBe(false);
  });
});
