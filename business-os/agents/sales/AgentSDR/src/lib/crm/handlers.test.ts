import assert from "node:assert/strict";
import test from "node:test";
import { classifiedIntoDoNotContactSubcategory, detectsExplicitDncIntent } from "./handlers";

test("explicit DNC detection matches direct first-person requests", () => {
  assert.equal(detectsExplicitDncIntent("Please unsubscribe me from these emails."), true);
  assert.equal(detectsExplicitDncIntent("Don't contact me again."), true);
  assert.equal(detectsExplicitDncIntent("Stop messaging me"), true);
  assert.equal(detectsExplicitDncIntent("No more calls please"), true);
});

test("explicit DNC detection avoids ordinary negative sales intent", () => {
  assert.equal(detectsExplicitDncIntent("Not interested right now."), false);
  assert.equal(detectsExplicitDncIntent("Please don't stop sending the monthly report."), false);
  assert.equal(detectsExplicitDncIntent("We selected another vendor."), false);
});

// The seeded "Do Not Contact" subcategory has no assigned sequence. Unlike the
// regex-based `detectsExplicitDncIntent` above (which fires on the raw message
// text), this covers the AI classifier independently steering into that same
// subcategory — the case handleClassificationJob must also suppress outreach for.
test("recognizes an applied classification into the seeded Do Not Contact subcategory", () => {
  const subcategories = [
    { id: "sub-dnc", categoryKey: "not_interested", key: "do_not_contact", name: "Do Not Contact", reviewRequired: false },
    { id: "sub-timing", categoryKey: "not_interested", key: "not_required_now", name: "Not Required Right Now", reviewRequired: false },
  ] as const;

  assert.equal(
    classifiedIntoDoNotContactSubcategory({ applied: true, stale: false }, "sub-dnc", subcategories),
    true,
  );
});

test("does not flag a different subcategory, an unapplied result, a stale result, or a missing id", () => {
  const subcategories = [
    { id: "sub-dnc", categoryKey: "not_interested", key: "do_not_contact", name: "Do Not Contact", reviewRequired: false },
    { id: "sub-timing", categoryKey: "not_interested", key: "not_required_now", name: "Not Required Right Now", reviewRequired: false },
  ] as const;

  assert.equal(
    classifiedIntoDoNotContactSubcategory({ applied: true, stale: false }, "sub-timing", subcategories),
    false,
  );
  assert.equal(
    classifiedIntoDoNotContactSubcategory({ applied: false, stale: false }, "sub-dnc", subcategories),
    false,
  );
  assert.equal(
    classifiedIntoDoNotContactSubcategory({ applied: true, stale: true }, "sub-dnc", subcategories),
    false,
  );
  assert.equal(
    classifiedIntoDoNotContactSubcategory({ applied: true, stale: false }, null, subcategories),
    false,
  );
});
