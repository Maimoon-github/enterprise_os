import { describe, expect, test } from "bun:test";
import { TRANSCRIPT_STUCK_AFTER_MS, transcriptLooksStuck } from "./transcriptState";

describe("transcriptLooksStuck", () => {
  const endedAt = "2026-09-29T10:00:00.000Z";
  const at = (ms: number) => Date.parse(endedAt) + ms;
  test("a pending transcript is stuck only once the server would let a retry take it over", () => {
    const call = { transcriptStatus: "pending" as const, endedAt, createdAt: endedAt };
    expect(transcriptLooksStuck(call, at(TRANSCRIPT_STUCK_AFTER_MS - 1))).toBe(false);
    expect(transcriptLooksStuck(call, at(TRANSCRIPT_STUCK_AFTER_MS + 1))).toBe(true);
  });
  test("never for a transcript that is done, failed, or not started", () => {
    for (const transcriptStatus of ["done", "failed", "none"] as const) {
      expect(transcriptLooksStuck({ transcriptStatus, endedAt, createdAt: endedAt }, at(60 * 60 * 1000))).toBe(false);
    }
  });
  test("falls back to when the call was created", () => {
    expect(transcriptLooksStuck({ transcriptStatus: "pending", endedAt: null, createdAt: endedAt }, at(TRANSCRIPT_STUCK_AFTER_MS + 1))).toBe(true);
  });
});
