import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  crmWorkerPositiveInteger,
  registerCrmJobHandler,
  registerCrmJobHandlers,
  registeredCrmJobKinds,
} from "./worker";

describe("CRM worker handler registry", () => {
  it("registers all three non-sending job kinds and unregisters safely", () => {
    const handler = async () => {};
    const unregister = registerCrmJobHandlers({
      classification: handler,
      initialDraft: handler,
      dueFollowupDraft: handler,
    });
    assert.deepEqual(new Set(registeredCrmJobKinds()), new Set([
      "classification",
      "initial_draft",
      "due_followup_draft",
    ]));
    unregister();
    assert.deepEqual(registeredCrmJobKinds(), []);
  });

  it("does not let an older registration unregister its replacement", () => {
    const unregisterOld = registerCrmJobHandler("classification", async () => {});
    const unregisterNew = registerCrmJobHandler("classification", async () => {});
    unregisterOld();
    assert.deepEqual(registeredCrmJobKinds(), ["classification"]);
    unregisterNew();
    assert.deepEqual(registeredCrmJobKinds(), []);
  });
});

describe("CRM worker configuration", () => {
  it("accepts bounded integers and falls back for invalid values", () => {
    assert.equal(crmWorkerPositiveInteger("8", 4, 1), 8);
    assert.equal(crmWorkerPositiveInteger("8.9", 4, 1), 8);
    assert.equal(crmWorkerPositiveInteger("invalid", 4, 1), 4);
    assert.equal(crmWorkerPositiveInteger("0", 4, 1), 4);
  });
});
