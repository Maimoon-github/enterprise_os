import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { CrmConfigurationValidationError } from "@/lib/crm/categories";
import { parseInboxReplyRequest } from "./replyRequest";

const DRAFT_ID = "2f6d0a3e-6f4b-4c8e-9b1a-3f2e1d0c9b8a";

describe("parseInboxReplyRequest", () => {
  test("accepts the composer payload and ignores `to`", () => {
    const parsed = parseInboxReplyRequest({
      to: ["lead@example.com"],
      cc: [],
      bcc: [],
      subject: " Re: hello ",
      text: "Thanks, sounds good.",
      html: "<p>Thanks, sounds good.</p>",
    });
    assert.deepEqual(parsed, {
      subject: "Re: hello",
      text: "Thanks, sounds good.",
      html: "<p>Thanks, sounds good.</p>",
      cc: [],
      bcc: [],
      draft: null,
    });
  });

  test("cc and bcc are normalized, deduplicated and kept apart", () => {
    const parsed = parseInboxReplyRequest({
      to: ["someone-else@example.com"],
      cc: [" Boss@Example.com ", { email: "boss@example.com" }, "peer@example.com"],
      bcc: ["peer@example.com", "audit@example.com"],
      subject: "s",
      text: "t",
    });
    assert.deepEqual(parsed.cc, ["boss@example.com", "peer@example.com"]);
    assert.deepEqual(parsed.bcc, ["audit@example.com"]);
  });

  test("invalid or oversized cc/bcc is rejected", () => {
    assert.throws(() => parseInboxReplyRequest({ subject: "s", text: "t", cc: ["nope"] }), /invalid email address: nope/);
    assert.throws(() => parseInboxReplyRequest({ subject: "s", text: "t", bcc: "a@b.co" }), CrmConfigurationValidationError);
    assert.throws(() => parseInboxReplyRequest({ subject: "s", text: "t", cc: [42] }), CrmConfigurationValidationError);
    const many = Array.from({ length: 21 }, (_, i) => `p${i}@example.com`);
    assert.throws(() => parseInboxReplyRequest({ subject: "s", text: "t", cc: many }), /at most 20/);
  });

  test("empty or missing html means text only", () => {
    assert.equal(parseInboxReplyRequest({ subject: "s", text: "t", html: "  " }).html, null);
    assert.equal(parseInboxReplyRequest({ subject: "s", text: "t" }).html, null);
    assert.equal(parseInboxReplyRequest({ subject: "s", text: "t", html: null }).html, null);
  });

  test("subject and text are required, since CRM email drafts need both", () => {
    assert.throws(() => parseInboxReplyRequest({ text: "t" }), CrmConfigurationValidationError);
    assert.throws(() => parseInboxReplyRequest({ subject: "  ", text: "t" }), CrmConfigurationValidationError);
    assert.throws(() => parseInboxReplyRequest({ subject: "s", text: "" }), CrmConfigurationValidationError);
    assert.throws(() => parseInboxReplyRequest({ subject: "s", text: 42 }), CrmConfigurationValidationError);
  });

  test("draftId carries its revision", () => {
    const parsed = parseInboxReplyRequest({ subject: "s", text: "t", draftId: DRAFT_ID, revision: 3 });
    assert.deepEqual(parsed.draft, { id: DRAFT_ID, revision: 3 });
    assert.equal(parseInboxReplyRequest({ subject: "s", text: "t", draftId: null }).draft, null);
  });

  test("draftId without a usable revision is rejected", () => {
    assert.throws(() => parseInboxReplyRequest({ subject: "s", text: "t", draftId: DRAFT_ID }), /revision/);
    assert.throws(() => parseInboxReplyRequest({ subject: "s", text: "t", draftId: DRAFT_ID, revision: "3" }), /revision/);
    assert.throws(() => parseInboxReplyRequest({ subject: "s", text: "t", draftId: DRAFT_ID, revision: -1 }), /revision/);
    assert.throws(() => parseInboxReplyRequest({ subject: "s", text: "t", draftId: "not-a-uuid", revision: 1 }), /UUID/);
  });

  test("non-object bodies are rejected", () => {
    assert.throws(() => parseInboxReplyRequest(null), CrmConfigurationValidationError);
    assert.throws(() => parseInboxReplyRequest(["subject"]), CrmConfigurationValidationError);
    assert.throws(() => parseInboxReplyRequest("subject"), CrmConfigurationValidationError);
  });
});
