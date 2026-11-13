import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  CrmConfigurationValidationError,
  parseCreateSubcategoryInput,
  parseUpdateSubcategoryInput,
  slugifySubcategoryKey,
} from "./categories";
import {
  parseCreateKnowledgeDocumentInput,
  parseUpdateKnowledgeDocumentInput,
} from "./knowledge-service";
import {
  parseAssignmentInput,
  parseCreateSequenceInput,
  parseSequenceSteps,
  validatePublishableSteps,
} from "./sequences";

const PIPELINE_ID = "00000000-0000-0000-0000-000000000001";
const SEQUENCE_ID = "00000000-0000-4000-8000-000000000002";

describe("CRM configuration validation", () => {
  test("generates stable immutable-style subcategory keys", () => {
    assert.equal(slugifySubcategoryKey("  Démo Requested!  "), "demo_requested");
    assert.equal(slugifySubcategoryKey("123 Priority"), "subcategory_123_priority");
  });

  test("accepts only fixed categories and editable subcategory fields", () => {
    const parsed = parseCreateSubcategoryInput({
      pipelineId: PIPELINE_ID,
      categoryKey: "interested",
      name: "Demo requested",
    });
    assert.equal(parsed.categoryKey, "interested");
    assert.equal(parsed.reviewRequired, false);
    assert.throws(
      () => parseCreateSubcategoryInput({ ...parsed, categoryKey: "maybe" }),
      CrmConfigurationValidationError,
    );
    assert.throws(
      () => parseUpdateSubcategoryInput({ categoryKey: "customer" }),
      /Unknown field: categoryKey/,
    );
  });

  test("derives channel-neutral sequence step semantics", () => {
    const sequence = parseCreateSequenceInput({
      name: "Demo follow-up",
      steps: [
        { name: "Reply", delayMinutes: 0, aiInstructions: "Answer", subjectTemplate: "Re: demo" },
        { name: "Follow-up", delayMinutes: 1_440, aiInstructions: "Check in" },
      ],
    });
    assert.equal(sequence.steps.length, 2);
    assert.doesNotThrow(() => validatePublishableSteps(sequence.steps));
    assert.equal(sequence.steps[0]?.subjectTemplate, "Re: demo");
    assert.throws(
      () => parseCreateSequenceInput({ name: "Legacy", channel: "email", steps: [] }),
      /Unknown field: channel/,
    );
    assert.throws(() => validatePublishableSteps([]), /immediate reply/);
    assert.throws(
      () => parseSequenceSteps([
        { name: "Reply", delayMinutes: 0, aiInstructions: "Answer" },
        { name: "Follow-up", delayMinutes: 0, aiInstructions: "Too soon" },
      ]),
      /positive delay/,
    );
  });

  test("supports explicit assignment clearing and validates IDs", () => {
    assert.deepEqual(parseAssignmentInput({ sequenceId: null }), { sequenceId: null });
    assert.deepEqual(parseAssignmentInput({ sequenceId: SEQUENCE_ID }), { sequenceId: SEQUENCE_ID });
    assert.throws(() => parseAssignmentInput({ sequenceId: "not-an-id" }), /UUID/);
  });

  test("validates versioned Knowledge input and archive-only lifecycle", () => {
    const created = parseCreateKnowledgeDocumentInput({
      title: "Pricing FAQ",
      kind: "pricing",
      tags: ["Enterprise", "Annual"],
      alwaysInclude: true,
      content: "Current approved pricing guidance.",
    });
    assert.deepEqual(created.tags, ["enterprise", "annual"]);
    assert.deepEqual(parseUpdateKnowledgeDocumentInput({ active: false }), { active: false });
    assert.throws(
      () => parseCreateKnowledgeDocumentInput({ ...created, kind: "secret" }),
      /supported Knowledge document kind/,
    );
    assert.throws(
      () => parseUpdateKnowledgeDocumentInput({ tags: ["same", "same"] }),
      /duplicates/,
    );
    assert.throws(() => parseUpdateKnowledgeDocumentInput({}), /editable field/);
  });
});
