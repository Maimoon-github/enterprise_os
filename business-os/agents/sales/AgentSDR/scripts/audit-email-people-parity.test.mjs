import { describe, expect, test } from "bun:test";
import { compareEmailParityRow, legacyEmailVariables, substituteVariables } from "./audit-email-people-parity.ts";

const base = {
  id: "lead-1",
  campaignId: "campaign-1",
  legacyEmail: "person@example.com",
  legacyFirstName: "Legacy",
  legacyLastName: "Person",
  legacyCompany: "Legacy Co",
  legacyCustomFields: { IceBreaker: "Relevant detail", firstName: "must-not-win" },
  sequenceStatus: "pending",
  currentStep: 0,
  sequence: [{ subject: "Hi {{FIRSTNAME}}", body: "{{icebreaker}} at {{company}}", waitDays: 0 }],
  personId: "person-1",
  personEmail: "person@example.com",
  personLinkedinUrl: null,
  personFirstName: null,
  personLastName: null,
  personFullName: null,
  personTitle: null,
  personRaw: { IceBreaker: "Relevant detail", firstName: "Legacy", lastName: "Person", company: "Legacy Co" },
  companyDomain: null,
  companyName: null,
  companyLinkedinUrl: null,
  companyRaw: null,
};

describe("Email People parity", () => {
  test("models legacy standard-field precedence over custom fields", () => {
    const variables = legacyEmailVariables(base);
    expect(substituteVariables("{{FIRSTNAME}} {{icebreaker}}", variables)).toBe("Legacy Relevant detail");
  });

  test("passes when legacy raw migration preserves pending rendering", () => {
    expect(compareEmailParityRow(base)).toEqual({ reasons: [], changedSteps: [] });
  });

  test("fails closed when a recipient or pending rendered step changes", () => {
    const result = compareEmailParityRow({
      ...base,
      personEmail: "other@example.com",
      personRaw: { ...base.personRaw, IceBreaker: "Different" },
    });
    expect(result.reasons).toEqual(["recipient_changed", "pending_render_changed"]);
    expect(result.changedSteps).toEqual([0]);
  });

  test("does not block on completed steps that will never send again", () => {
    expect(compareEmailParityRow({
      ...base,
      sequenceStatus: "sequence_completed",
      personRaw: { different: "value" },
    })).toEqual({ reasons: [], changedSteps: [] });
  });

  test("accepts People-native enrollments that intentionally have no legacy snapshot", () => {
    expect(compareEmailParityRow({
      ...base,
      legacyEmail: null,
      legacyFirstName: null,
      legacyLastName: null,
      legacyCompany: null,
      legacyCustomFields: {},
      personEmail: "new-person@example.com",
      personFirstName: "New",
      personRaw: { segment: "enterprise" },
      sequence: [{ subject: "Hi {{firstName}}", body: "{{segment}}", waitDays: 0 }],
    })).toEqual({ reasons: [], changedSteps: [] });
  });
});
