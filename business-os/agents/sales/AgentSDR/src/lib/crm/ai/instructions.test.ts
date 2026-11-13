import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { formatAiInstructions, MAX_AI_INSTRUCTIONS_TOTAL_LENGTH, renderAiInstructions } from "./instructions";

describe("AI instruction blocks", () => {
  test("render as titled sections, skipping blocks with no content", () => {
    assert.equal(
      renderAiInstructions([
        { id: "a", title: " Tone ", content: " Be brief. " },
        { id: "b", title: "Draft in progress", content: "  " },
        { id: "c", title: "", content: "No discounts." },
      ]),
      "## Tone\nBe brief.\n\nNo discounts.",
    );
  });

  test("nothing to send is null, whatever jsonb held", () => {
    for (const value of [null, undefined, [], "text", {}, [null, 5, { title: "Only a title" }]]) {
      assert.equal(formatAiInstructions(value), null);
    }
  });

  test("the prompt text is capped even if the stored list is not", () => {
    const text = formatAiInstructions([{ id: "a", title: "", content: "x".repeat(MAX_AI_INSTRUCTIONS_TOTAL_LENGTH + 50) }]);
    assert.equal(text?.length, MAX_AI_INSTRUCTIONS_TOTAL_LENGTH);
  });
});
