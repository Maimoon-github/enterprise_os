import { describe, expect, test } from "bun:test";
import { composeAgentBrief } from "./brief";

describe("composeAgentBrief", () => {
  test("campaign instructions, then this call, then the lead's own instructions", () => {
    const brief = composeAgentBrief({
      campaignInstructions: "We sell storefronts.",
      purpose: "reach",
      stepInstructions: "Second try.",
      leadInstructions: "Met at the Mumbai meetup.",
    });
    expect(brief).toBe("We sell storefronts.\n\nThis call: Second try.\n\nFor this person in particular: Met at the Mumbai meetup.");
  });
  test("no lead instructions, no extra section", () => {
    expect(composeAgentBrief({ campaignInstructions: "X", purpose: "reach", stepInstructions: "Y", leadInstructions: "  " })).toBe("X\n\nThis call: Y");
  });
  test("an incoming call: they called back, and the first step says what it was about", () => {
    const brief = composeAgentBrief({
      campaignInstructions: "We sell storefronts.",
      purpose: "inbound",
      stepInstructions: "Ask about their store's conversion rate.",
      leadInstructions: "Prefers Hindi.",
    });
    expect(brief).toContain("They called this number back");
    expect(brief).toContain("What you were reaching out about: Ask about their store's conversion rate.");
    expect(brief).toContain("For this person in particular: Prefers Hindi.");
    expect(brief).not.toContain("Introduce yourself and find out");
  });
});
