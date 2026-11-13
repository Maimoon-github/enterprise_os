import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { decideProviderCollision } from "../../../scripts/resolve-linkedin-provider-collisions.ts";

const collision = (overrides = {}) => ({
  providerId: "provider-1",
  linkedinAccountId: "account-1",
  leadIds: ["newer", "older"],
  requestSentAts: [new Date("2026-08-01"), new Date("2026-07-01")],
  statuses: ["REQUEST_SENT", "REQUEST_SENT"],
  messageCounts: [1, 1],
  connectionCounts: [0, 0],
  ...overrides,
});

describe("decideProviderCollision", () => {
  it("keeps the most recent request selected by the SQL ordering", () => {
    assert.deepEqual(decideProviderCollision(collision()), {
      survivorId: "newer",
      supersededIds: ["older"],
    });
  });

  it("refuses to supersede a Lead with later campaign activity", () => {
    assert.throws(() => decideProviderCollision(collision({ statuses: ["REQUEST_SENT", "CONNECTED"] })), /beyond REQUEST_SENT/);
    assert.throws(() => decideProviderCollision(collision({ messageCounts: [1, 2] })), /unexpected message or connection history/);
  });
});
