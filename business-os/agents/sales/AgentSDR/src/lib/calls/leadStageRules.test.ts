import { describe, expect, test } from "bun:test";
import { buildClassificationContext } from "@/lib/crm/context";
import {
  buildCallClassificationInput,
  followUpFromSuggestion,
  formatTranscriptForClassification,
  humanStageSetSinceCall,
  isLeadStageCategory,
  leadStageTargetError,
  pickRepresentativeRecord,
} from "./leadStageRules";

const PIPELINE = "11111111-1111-4111-8111-111111111111";
const SUB = "22222222-2222-4222-8222-222222222222";

describe("leadStageTargetError", () => {
  const subcategory = { pipelineId: PIPELINE, categoryKey: "interested", active: true };

  test("a category alone is always valid", () => {
    expect(leadStageTargetError({ categoryKey: "other", subcategoryId: null, subcategory: null, pipelineId: PIPELINE })).toBeNull();
  });

  test("a subcategory in the record's pipeline and the chosen category is valid", () => {
    expect(leadStageTargetError({ categoryKey: "interested", subcategoryId: SUB, subcategory, pipelineId: PIPELINE })).toBeNull();
  });

  test("an unknown id, or one from another pipeline, does not exist", () => {
    expect(leadStageTargetError({ categoryKey: "interested", subcategoryId: SUB, subcategory: null, pipelineId: PIPELINE }))
      .toBe("That stage does not exist");
    expect(leadStageTargetError({
      categoryKey: "interested",
      subcategoryId: SUB,
      subcategory: { ...subcategory, pipelineId: "other" },
      pipelineId: PIPELINE,
    })).toBe("That stage does not exist");
  });

  test("a subcategory under another category is rejected", () => {
    expect(leadStageTargetError({ categoryKey: "not_interested", subcategoryId: SUB, subcategory, pipelineId: PIPELINE }))
      .toBe("That stage does not belong to the chosen category");
  });

  test("an archived subcategory cannot be newly assigned", () => {
    expect(leadStageTargetError({
      categoryKey: "interested",
      subcategoryId: SUB,
      subcategory: { ...subcategory, active: false },
      pipelineId: PIPELINE,
    })).toBe("That stage has been archived");
  });
});

test("isLeadStageCategory accepts exactly the four fixed categories", () => {
  for (const key of ["interested", "customer", "not_interested", "other"]) expect(isLeadStageCategory(key)).toBe(true);
  expect(isLeadStageCategory("meeting_requested")).toBe(false);
  expect(isLeadStageCategory(null)).toBe(false);
});

describe("pickRepresentativeRecord", () => {
  const at = (iso: string) => new Date(iso);
  test("prefers the default pipeline, then the most recently updated", () => {
    const records = [
      { id: "a", isDefaultPipeline: false, updatedAt: at("2026-09-30T00:00:00Z") },
      { id: "b", isDefaultPipeline: true, updatedAt: at("2026-09-01T00:00:00Z") },
      { id: "c", isDefaultPipeline: true, updatedAt: at("2026-09-02T00:00:00Z") },
    ];
    expect(pickRepresentativeRecord(records)?.id).toBe("c");
    expect(pickRepresentativeRecord(records.slice(0, 1))?.id).toBe("a");
    expect(pickRepresentativeRecord([])).toBeNull();
  });
});

describe("the transcript as a classifier input", () => {
  const transcript = {
    summary: "The lead asked for a demo next Tuesday.",
    utterances: [
      { startSeconds: 0, speaker: "rep" as const, text: "Hi, this is Asha from Acme." },
      { startSeconds: 4, speaker: "lead" as const, text: " Haan, send me a demo invite for Tuesday. " },
    ],
  };

  test("labels each line Rep or Lead and leads with the summary", () => {
    const text = formatTranscriptForClassification(transcript);
    expect(text).toContain("Summary: The lead asked for a demo next Tuesday.");
    expect(text).toContain("Rep: Hi, this is Asha from Acme.\nLead: Haan, send me a demo invite for Tuesday.");
    expect(text.indexOf("Summary:")).toBeLessThan(text.indexOf("Rep:"));
  });

  test("the call stands in for the latest inbound message and is the whole conversation", () => {
    const occurredAt = new Date("2026-09-30T10:00:00Z");
    const input = buildCallClassificationInput({
      callId: "call-1",
      occurredAt,
      transcript,
      categories: [{ key: "interested", label: "Interested" }],
      subcategories: [],
      person: { id: "p1", fullName: "Rahul" },
      company: null,
      currentClassification: { categoryKey: null, subcategoryKey: null, categoryLocked: false },
      campaign: { id: "camp-1", name: "Q4 founders", description: null },
      knowledge: [],
      policy: { autoApplyConfidence: 0.85, reviewOther: true, customerRequiresReview: true },
    });
    expect(input.latestInboundMessage).toMatchObject({
      id: "call-1",
      channel: "whatsapp_call",
      direction: "inbound",
      sentAt: occurredAt,
    });
    expect(input.latestInboundMessage.bodyText).toContain("Lead: Haan");
    expect(input.recentConversation).toEqual([input.latestInboundMessage]);
    expect(input.campaignSummary).toMatchObject({ campaignId: "camp-1", name: "Q4 founders" });
    expect(input.policy.autoApplyConfidence).toBe(0.85);

    // The CRM's own context builder takes it as it would a reply.
    const context = buildClassificationContext(input);
    expect(context.snapshot.latestInboundMessage.channel).toBe("whatsapp_call");
    expect(context.prompt).toContain("Lead: Haan, send me a demo invite for Tuesday.");
  });
});

describe("humanStageSetSinceCall — a person's stage outranks the transcript", () => {
  const callStartedAt = new Date("2026-09-30T10:00:00Z");

  test("only a human-set stage is protected", () => {
    for (const categorySource of ["ai", "integration", null] as const) {
      expect(humanStageSetSinceCall({ categorySource, lastHumanStageAt: new Date("2026-09-30T11:00:00Z"), callStartedAt })).toBe(false);
    }
  });

  test("set during or after the call: kept", () => {
    expect(humanStageSetSinceCall({ categorySource: "human", lastHumanStageAt: callStartedAt, callStartedAt })).toBe(true);
    expect(humanStageSetSinceCall({ categorySource: "human", lastHumanStageAt: new Date("2026-09-30T10:05:00Z"), callStartedAt })).toBe(true);
  });

  test("set before the call: the call is newer evidence", () => {
    expect(humanStageSetSinceCall({ categorySource: "human", lastHumanStageAt: new Date("2026-09-29T10:00:00Z"), callStartedAt })).toBe(false);
  });

  test("a human stage that cannot be dated is kept", () => {
    expect(humanStageSetSinceCall({ categorySource: "human", lastHumanStageAt: null, callStartedAt })).toBe(true);
  });
});

describe("followUpFromSuggestion", () => {
  const now = new Date("2026-09-30T10:00:00Z");
  test("a future suggestion fills an empty follow-up", () => {
    expect(followUpFromSuggestion("2026-10-06T09:00:00Z", null, now)).toEqual(new Date("2026-10-06T09:00:00Z"));
  });
  test("an existing follow-up is never replaced", () => {
    expect(followUpFromSuggestion("2026-10-06T09:00:00Z", new Date("2026-10-01T00:00:00Z"), now)).toBeNull();
  });
  test("no suggestion, a past one, or garbage: nothing", () => {
    expect(followUpFromSuggestion(null, null, now)).toBeNull();
    expect(followUpFromSuggestion("2026-09-01T00:00:00Z", null, now)).toBeNull();
    expect(followUpFromSuggestion("next tuesday", null, now)).toBeNull();
  });
});
