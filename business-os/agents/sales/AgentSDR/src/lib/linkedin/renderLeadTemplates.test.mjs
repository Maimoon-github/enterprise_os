import { describe, expect, test } from "bun:test";
import { renderLeadTemplates } from "./renderLeadTemplates.ts";

describe("renderLeadTemplates", () => {
  test("renders lead-specific values without changing missing templates", () => {
    expect(renderLeadTemplates({
      invitationMessage: null,
      acceptanceMessage: "Hi {{firstname}} from {{company}}",
      followUp1Message: "Following up with {{firstName}}",
      followUp2Message: null,
      followUp3Message: null,
    }, {
      firstName: "Varun",
      company: "Dr Sharda Ayurveda",
    })).toEqual({
      invitationMessage: null,
      acceptanceMessage: "Hi Varun from Dr Sharda Ayurveda",
      followUp1Message: "Following up with Varun",
      followUp2Message: null,
      followUp3Message: null,
    });
  });
});
