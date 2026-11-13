import { describe, expect, test } from "bun:test";
import {
  aiCampaignState,
  aiLaunchBlocker,
  aiSequencesError,
  aiSettingsError,
  aiStepLabel,
  callsPerDayLimit,
  describeStepKey,
  httpsUrl,
  previewAiMessage,
} from "./api";
import { DEFAULT_BOOKING_MESSAGE, DEFAULT_CHASE_STEPS, DEFAULT_REACH_STEPS } from "./contract";

const settings = { goal: "book_meeting" as const, instructions: "Call founders", bookingUrl: "https://cal.com/acme/30min", bookingMessage: DEFAULT_BOOKING_MESSAGE, maxCallbacks: 2 };

describe("aiLaunchBlocker", () => {
  const ready = { numbers: 1, steps: DEFAULT_REACH_STEPS, instructions: "x", goal: "book_meeting" as const, bookingUrl: "https://cal.com/a/b", leads: 3 };
  test("a complete campaign has no blocker", () => expect(aiLaunchBlocker(ready)).toBeNull());
  test("needs a number, a call step, instructions, leads", () => {
    expect(aiLaunchBlocker({ ...ready, numbers: 0 })).toContain("number");
    expect(aiLaunchBlocker({ ...ready, steps: [DEFAULT_REACH_STEPS[2]!] })).toContain("call");
    expect(aiLaunchBlocker({ ...ready, instructions: "  " })).toContain("instructions");
    expect(aiLaunchBlocker({ ...ready, leads: 0 })).toContain("lead");
  });
  test("a booking link is required unless the goal is a hand-over", () => {
    expect(aiLaunchBlocker({ ...ready, bookingUrl: null })).toContain("booking link");
    expect(aiLaunchBlocker({ ...ready, bookingUrl: null, goal: "either" })).toContain("booking link");
    expect(aiLaunchBlocker({ ...ready, bookingUrl: null, goal: "human_callback" })).toBeNull();
  });
});

describe("aiSettingsError", () => {
  test("accepts valid settings", () => expect(aiSettingsError(settings)).toBeNull());
  test("the booking link must be https", () => {
    expect(aiSettingsError({ ...settings, bookingUrl: "http://cal.com/x" })).toContain("https");
    expect(aiSettingsError({ ...settings, bookingUrl: "cal.com/x" })).toContain("https");
  });
  test("the booking message needs {{bookingLink}} when a link is set", () => {
    expect(aiSettingsError({ ...settings, bookingMessage: "Book here" })).toContain("{{bookingLink}}");
    expect(aiSettingsError({ ...settings, bookingUrl: null, bookingMessage: "Book here" })).toBeNull();
  });
  test("instructions and call-backs are bounded", () => {
    expect(aiSettingsError({ ...settings, instructions: "x".repeat(4001) })).toContain("4000");
    expect(aiSettingsError({ ...settings, maxCallbacks: 4 })).toContain("between 0 and 3");
    expect(aiSettingsError({ ...settings, maxCallbacks: 0 })).toBeNull();
  });
});

describe("aiSequencesError", () => {
  test("the defaults are valid", () => expect(aiSequencesError(DEFAULT_REACH_STEPS, DEFAULT_CHASE_STEPS)).toBeNull());
  test("the chase may be empty, the reach may not", () => {
    expect(aiSequencesError(DEFAULT_REACH_STEPS, [])).toBeNull();
    expect(aiSequencesError([], [])).toContain("Reach them");
  });
  test("names which sequence is wrong", () => {
    expect(aiSequencesError(DEFAULT_REACH_STEPS, [{ id: "a", kind: "message", delayHours: 1, body: "" }])).toContain("haven't booked");
  });
});

describe("helpers", () => {
  test("httpsUrl", () => {
    expect(httpsUrl(" https://cal.com/acme ")).toBe("https://cal.com/acme");
    expect(httpsUrl("javascript:alert(1)")).toBeNull();
    expect(httpsUrl("https://localhost")).toBeNull();
  });
  test("previewAiMessage fills known fields and leaves the rest", () => {
    expect(previewAiMessage("Hi {{firstName}} {{ agentName }} {{nope}}", { firstName: "Priya", agentName: "Riya" })).toBe("Hi Priya Riya {{nope}}");
  });
  test("aiStepLabel counts per kind", () => {
    expect(aiStepLabel(DEFAULT_REACH_STEPS, 0, false)).toBe("Call 1 of 3");
    expect(aiStepLabel(DEFAULT_REACH_STEPS, 2, false)).toBe("Message 1 of 1");
    expect(aiStepLabel(DEFAULT_REACH_STEPS, 3, true)).toBe("Call 3 of 3 (chasing the booking)");
    expect(aiStepLabel(DEFAULT_REACH_STEPS, 9, false)).toBeNull();
  });
  test("describeStepKey reads the engine's keys, retries included", () => {
    expect(describeStepKey("reach:call-1")).toMatchObject({ phase: "reach", stepId: "call-1" });
    expect(describeStepKey("retry:chase:chase-call-1:2")).toMatchObject({ phase: "chase", stepId: "chase-call-1" });
    expect(describeStepKey("callback:1")).toMatchObject({ phase: "system", stepId: null, label: "Call back 1" });
    expect(describeStepKey("booking-link").label).toBe("Booking link");
  });
  test("aiCampaignState", () => {
    expect(aiCampaignState({ launchedAt: null, status: "paused" })).toBe("draft");
    expect(aiCampaignState({ launchedAt: "2026-10-01", status: "paused" })).toBe("paused");
    expect(aiCampaignState({ launchedAt: new Date(), status: "active" })).toBe("active");
  });
  test("callsPerDayLimit uses each number's own limit, else the rule", () => {
    expect(callsPerDayLimit([{ callsPerDay: 10 }, { callsPerDay: null }], 30)).toBe(40);
  });
});
