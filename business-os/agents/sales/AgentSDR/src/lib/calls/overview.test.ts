import { describe, expect, test } from "bun:test";
import { outcomeForCall, resolveTimeZone, summarizeCalls } from "./overview";

describe("resolveTimeZone", () => {
  test("keeps a valid IANA zone", () => {
    expect(resolveTimeZone("Asia/Kolkata")).toBe("Asia/Kolkata");
  });
  test("falls back to UTC", () => {
    expect(resolveTimeZone("Not/AZone")).toBe("UTC");
    expect(resolveTimeZone("")).toBe("UTC");
    expect(resolveTimeZone(null)).toBe("UTC");
    expect(resolveTimeZone("'; DROP TABLE x;--")).toBe("UTC");
  });
});

describe("outcomeForCall", () => {
  test("maps statuses through the contact call status", () => {
    expect(outcomeForCall({ status: "recorded", error: null })).toBe("connected");
    expect(outcomeForCall({ status: "failed", error: "Upload failed: 500" })).toBe("connected");
    expect(outcomeForCall({ status: "failed", error: "This number isn't on WhatsApp" })).toBe("notOnWhatsApp");
    expect(outcomeForCall({ status: "failed", error: "boom" })).toBe("failed");
    expect(outcomeForCall({ status: "no_recording", error: null })).toBe("didNotPickUp");
    expect(outcomeForCall({ status: "in_progress", error: null })).toBe("inProgress");
  });
});

describe("summarizeCalls", () => {
  const groups = [
    { day: "2026-09-29", status: "recorded" as const, error: null, calls: 2, talk_ms: 120_000 },
    { day: "2026-09-29", status: "no_recording" as const, error: null, calls: 3, talk_ms: 0 },
    { day: "2026-09-30", status: "failed" as const, error: "Upload failed", calls: 1, talk_ms: 60_000 },
    { day: "2026-09-30", status: "failed" as const, error: "isn't on WhatsApp", calls: 1, talk_ms: 0 },
  ];
  const result = summarizeCalls(groups, ["2026-09-28", "2026-09-29", "2026-09-30"], new Map([["2026-09-30", 4]]), 5);

  test("totals", () => {
    expect(result.totals).toMatchObject({
      callsPlaced: 7,
      connected: 3,
      didNotPickUp: 3,
      notOnWhatsApp: 1,
      failed: 0,
      talkTimeMs: 180_000,
      avgTalkTimeMs: 60_000,
      messagesSent: 4,
      uniqueLeadsCalled: 5,
    });
    expect(result.totals.connectRate).toBeCloseTo(3 / 7);
  });
  test("zero-fills the day series", () => {
    expect(result.days).toEqual([
      { date: "2026-09-28", calls: 0, connected: 0, didNotPickUp: 0, messages: 0 },
      { date: "2026-09-29", calls: 5, connected: 2, didNotPickUp: 3, messages: 0 },
      { date: "2026-09-30", calls: 2, connected: 1, didNotPickUp: 0, messages: 4 },
    ]);
  });
  test("empty range has null rates", () => {
    const empty = summarizeCalls([], ["2026-09-30"], new Map(), 0);
    expect(empty.totals.connectRate).toBeNull();
    expect(empty.totals.avgTalkTimeMs).toBeNull();
  });
});
