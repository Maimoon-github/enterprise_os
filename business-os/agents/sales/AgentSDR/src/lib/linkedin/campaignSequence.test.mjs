import { describe, expect, test } from "bun:test";
import {
  EMPTY_LINKEDIN_SEQUENCE,
  LINKEDIN_SEQUENCE_STEPS,
  linkedinSequenceError,
  normalizeLinkedinSequence,
} from "./campaignSequence.ts";

describe("LinkedIn campaign sequence", () => {
  test("matches the fixed worker order and timing", () => {
    expect(LINKEDIN_SEQUENCE_STEPS.map(({ field, timing }) => ({ field, timing }))).toEqual([
      { field: "invitationMessage", timing: "Immediately" },
      { field: "acceptanceMessage", timing: "When accepted" },
      { field: "followUp1Message", timing: "1 day later" },
      { field: "followUp2Message", timing: "2 days later" },
      { field: "followUp3Message", timing: "3 days later" },
    ]);
  });

  test("normalizes whitespace and nullable values", () => {
    expect(normalizeLinkedinSequence({ invitationMessage: "  Hello  ", acceptanceMessage: null })).toEqual({
      ...EMPTY_LINKEDIN_SEQUENCE,
      invitationMessage: "Hello",
    });
  });

  test("allows optional messages but rejects gaps between follow-ups", () => {
    expect(linkedinSequenceError({ ...EMPTY_LINKEDIN_SEQUENCE, acceptanceMessage: "Thanks" })).toBeNull();
    expect(linkedinSequenceError({ ...EMPTY_LINKEDIN_SEQUENCE, followUp2Message: "Checking in" })).toBe(
      "Add follow-up 1 before adding a later follow-up",
    );
    expect(linkedinSequenceError({ ...EMPTY_LINKEDIN_SEQUENCE, followUp1Message: "One", followUp3Message: "Three" })).toBe(
      "Add follow-up 2 before adding a later follow-up",
    );
  });

  test("enforces the LinkedIn invitation limit", () => {
    expect(linkedinSequenceError({ ...EMPTY_LINKEDIN_SEQUENCE, invitationMessage: "x".repeat(300) })).toBeNull();
    expect(linkedinSequenceError({ ...EMPTY_LINKEDIN_SEQUENCE, invitationMessage: "x".repeat(301) })).toContain("300");
  });
});
