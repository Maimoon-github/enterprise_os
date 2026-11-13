import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { recommendSurvivor } from "../../../scripts/audit-linkedin-message-duplicates.ts";

function message(overrides = {}) {
  return {
    id: "m1",
    leadId: "lead-1",
    type: "FOLLOW_UP_1",
    linkedinMessageId: null,
    connectionId: "connection-1",
    seen: true,
    createdAt: new Date("2026-01-01T00:00:00.000Z"),
    leadStatus: "FOLLOW_UP_1_SENT",
    campaignId: "campaign-1",
    linkedinAccountId: "account-1",
    stageSentAt: new Date("2026-01-01T00:00:02.000Z"),
    textSha256: "same",
    textLength: 10,
    ...overrides,
  };
}

describe("recommendSurvivor", () => {
  it("selects the only provider-confirmed row when bodies match", () => {
    const result = recommendSurvivor([
      message(),
      message({ id: "m2", linkedinMessageId: "provider-1" }),
    ]);
    assert.deepEqual(result, {
      classification: "safe_candidate",
      survivorId: "m2",
      reason: "single_provider_confirmed_row",
    });
  });

  it("keeps the earliest row when duplicate rows share provider evidence", () => {
    const result = recommendSurvivor([
      message({ id: "later", linkedinMessageId: "provider-1", createdAt: new Date("2026-01-02T00:00:00Z") }),
      message({ id: "earlier", linkedinMessageId: "provider-1" }),
    ]);
    assert.equal(result.survivorId, "earlier");
    assert.equal(result.classification, "safe_candidate");
  });

  it("preserves close provider-confirmed duplicate deliveries under the earliest row", () => {
    const result = recommendSurvivor([
      message({ linkedinMessageId: "provider-1" }),
      message({ id: "m2", linkedinMessageId: "provider-2" }),
    ]);
    assert.equal(result.classification, "safe_candidate");
    assert.equal(result.survivorId, "m1");
    assert.equal(result.reason, "provider_confirmed_duplicate_delivery_within_10_seconds");
  });

  it("requires review for distinct provider IDs outside the safety window", () => {
    const result = recommendSurvivor([
      message({ linkedinMessageId: "provider-1" }),
      message({
        id: "m2",
        linkedinMessageId: "provider-2",
        createdAt: new Date("2026-01-01T00:00:11.000Z"),
      }),
    ]);
    assert.equal(result.classification, "manual_review");
    assert.equal(result.reason, "distinct_provider_message_ids_outside_safe_window");
  });

  it("requires review for conflicting message bodies", () => {
    const result = recommendSurvivor([
      message({ linkedinMessageId: "provider-1" }),
      message({ id: "m2", textSha256: "different" }),
    ]);
    assert.equal(result.classification, "manual_review");
    assert.equal(result.reason, "conflicting_message_texts");
  });

  it("requires review when no row has provider delivery evidence", () => {
    const result = recommendSurvivor([message(), message({ id: "m2" })]);
    assert.equal(result.classification, "manual_review");
    assert.equal(result.reason, "no_provider_delivery_evidence");
  });
});
