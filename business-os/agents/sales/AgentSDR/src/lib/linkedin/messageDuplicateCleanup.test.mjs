import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { decideDuplicateGroup } from "../../../scripts/mark-linkedin-message-duplicates.ts";

function row(overrides = {}) {
  return {
    id: "first",
    leadId: "lead-1",
    type: "ACCEPTANCE",
    text: "Thanks for connecting",
    linkedinMessageId: "provider-1",
    createdAt: new Date("2026-01-01T00:00:00.000Z"),
    ...overrides,
  };
}

describe("decideDuplicateGroup", () => {
  it("preserves all later provider deliveries under the earliest canonical row", () => {
    const decision = decideDuplicateGroup([
      row({ id: "third", linkedinMessageId: "provider-3", createdAt: new Date("2026-01-01T00:00:06.000Z") }),
      row(),
      row({ id: "second", linkedinMessageId: "provider-2", createdAt: new Date("2026-01-01T00:00:03.000Z") }),
    ]);
    assert.equal(decision.survivorId, "first");
    assert.deepEqual(decision.duplicateIds, ["second", "third"]);
    assert.equal(decision.deliveryWindowMs, 6000);
  });

  it("rejects conflicting bodies", () => {
    assert.throws(() => decideDuplicateGroup([
      row(),
      row({ id: "second", linkedinMessageId: "provider-2", text: "Different" }),
    ]), /message bodies differ/);
  });

  it("rejects rows outside the strict ten-second window", () => {
    assert.throws(() => decideDuplicateGroup([
      row(),
      row({ id: "second", linkedinMessageId: "provider-2", createdAt: new Date("2026-01-01T00:00:11.000Z") }),
    ]), /more than 10 seconds/);
  });
});
