import { describe, expect, test } from "bun:test";
import { CallApiError } from "@/lib/calls/sessions";
import { parseStationAiSettings } from "@/lib/calls/stationSettings";
import { DEFAULT_CHASE_STEPS, DEFAULT_REACH_STEPS } from "./contract";
import { foldStepRuns, normalizeSteps, parseAiLeadsQuery, parseStationIds, parseUpdateAiCampaignRequest, parseUpdateAiLeadRequest } from "./campaigns.server";

const campaign = { aiSteps: DEFAULT_REACH_STEPS, aiChaseSteps: DEFAULT_CHASE_STEPS };

describe("foldStepRuns", () => {
  test("lists every configured step in order, even before it has run", () => {
    const stats = foldStepRuns([], campaign);
    expect(stats.map((s) => s.key)).toEqual([
      "reach:call-1", "reach:call-2", "reach:message-1", "reach:call-3", "chase:chase-message-1", "chase:chase-call-1",
    ]);
    expect(stats.every((s) => s.attempted === 0)).toBe(true);
  });
  test("counts runs, folds retries into their step and keeps system steps apart", () => {
    const stats = foldStepRuns(
      [
        { stepKey: "reach:call-1", kind: "call", status: "done", result: "conversation", n: 3 },
        { stepKey: "reach:call-1", kind: "call", status: "failed", result: "error", n: 1 },
        { stepKey: "retry:reach:call-1:1", kind: "call", status: "done", result: "no_answer", n: 2 },
        { stepKey: "booking-link", kind: "message", status: "done", result: null, n: 4 },
      ],
      campaign,
    );
    const call1 = stats.find((s) => s.key === "reach:call-1")!;
    expect(call1).toMatchObject({ attempted: 6, done: 5, failed: 1, conversations: 3 });
    expect(stats.find((s) => s.label === "Booking link")).toMatchObject({ phase: "system", attempted: 4, kind: "message" });
  });
  test("a run of a step that was since removed still shows", () => {
    const stats = foldStepRuns([{ stepKey: "reach:gone", kind: "call", status: "done", result: null, n: 1 }], campaign);
    expect(stats.find((s) => s.stepId === "gone")?.label).toContain("removed");
  });
});

describe("normalizeSteps", () => {
  test("clears the first wait and trims text", () => {
    const [first, second] = normalizeSteps([
      { id: "a", kind: "call", delayHours: 5, instructions: "  hi  " },
      { id: "b", kind: "message", delayHours: 2.4, body: " yo " },
    ]);
    expect(first).toEqual({ id: "a", kind: "call", delayHours: 0, instructions: "hi" });
    expect(second).toEqual({ id: "b", kind: "message", delayHours: 2, body: "yo" });
  });
});

describe("request parsing", () => {
  test("PATCH rejects unknown fields and a bad booking link", () => {
    expect(() => parseUpdateAiCampaignRequest({ nope: 1 })).toThrow(CallApiError);
    expect(() => parseUpdateAiCampaignRequest({ bookingUrl: "http://x.com" })).toThrow("https");
    expect(parseUpdateAiCampaignRequest({ bookingUrl: "", agentName: "  Riya  ", agentVoice: "" })).toEqual({ bookingUrl: null, agentName: "Riya", agentVoice: null });
  });
  test("PATCH validates the voice and the status", () => {
    expect(() => parseUpdateAiCampaignRequest({ agentVoice: "Nobody" })).toThrow("voice");
    expect(() => parseUpdateAiCampaignRequest({ status: "archived" })).toThrow("status");
  });
  test("stationIds must be uuids, de-duplicated", () => {
    const id = "11111111-1111-4111-8111-111111111111";
    expect(parseStationIds({ stationIds: [id, id] })).toEqual([id]);
    expect(() => parseStationIds({ stationIds: ["x"] })).toThrow(CallApiError);
  });
  test("lead query and action", () => {
    expect(parseAiLeadsQuery(new URL("http://x/?status=booked&page=2&q=ann"))).toEqual({ status: "booked", q: "ann", page: 2, pageSize: undefined });
    expect(() => parseAiLeadsQuery(new URL("http://x/?status=nope"))).toThrow(CallApiError);
    expect(() => parseUpdateAiLeadRequest({ action: "delete" })).toThrow(CallApiError);
    expect(parseUpdateAiLeadRequest({ action: "requeue" })).toEqual({ action: "requeue" });
  });
});

describe("parseStationAiSettings", () => {
  test("blank (null) means the organization's rule", () => {
    expect(parseStationAiSettings({ callsPerDay: null, callingHours: null })).toEqual({ callsPerDay: null, callingHours: null });
  });
  test("checks the number against the sending rule's bounds", () => {
    expect(parseStationAiSettings({ callsPerDay: 25 })).toEqual({ callsPerDay: 25 });
    expect(() => parseStationAiSettings({ callsPerDay: 0 })).toThrow(CallApiError);
    expect(() => parseStationAiSettings({ callsPerDay: 1.5 })).toThrow(CallApiError);
    expect(() => parseStationAiSettings({ callsPerDay: 101 })).toThrow(CallApiError);
  });
  test("checks and normalizes hours", () => {
    const hours = { timezone: "Asia/Kolkata", days: [3, 1, 1], start: "10:00", end: "18:00" };
    expect(parseStationAiSettings({ callingHours: hours }).callingHours?.days).toEqual([1, 3]);
    expect(() => parseStationAiSettings({ callingHours: { ...hours, end: "09:00" } })).toThrow(CallApiError);
    expect(() => parseStationAiSettings({ callingHours: { ...hours, days: [] } })).toThrow(CallApiError);
    expect(() => parseStationAiSettings({ callingHours: { ...hours, timezone: "Mars/Base" } })).toThrow(CallApiError);
    expect(() => parseStationAiSettings({ other: 1 })).toThrow(CallApiError);
  });
});

describe("parseUpdateAiCampaignRequest knowledgeIds", () => {
  const id = "d13cecd7-6837-469b-b61e-ad21ef2144f4";
  test("keeps a list of ids once each, an empty list, or null for the default", () => {
    expect(parseUpdateAiCampaignRequest({ knowledgeIds: [id, id] }).knowledgeIds).toEqual([id]);
    expect(parseUpdateAiCampaignRequest({ knowledgeIds: [] }).knowledgeIds).toEqual([]);
    expect(parseUpdateAiCampaignRequest({ knowledgeIds: null }).knowledgeIds).toBeNull();
  });
  test("refuses anything that is not a list of document ids", () => {
    expect(() => parseUpdateAiCampaignRequest({ knowledgeIds: ["nope"] })).toThrow(CallApiError);
    expect(() => parseUpdateAiCampaignRequest({ knowledgeIds: id })).toThrow(CallApiError);
  });
});
