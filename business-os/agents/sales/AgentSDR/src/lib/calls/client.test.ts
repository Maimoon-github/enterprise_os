import { describe, expect, test } from "bun:test";
import { MIN_RECORDER_VERSION } from "./contract";
import { isRecorderOutdated } from "./client";

describe("isRecorderOutdated", () => {
  test("the minimum version itself is current", () => {
    expect(isRecorderOutdated(MIN_RECORDER_VERSION)).toBe(false);
  });
  test("an older build is outdated, compared numerically not as text", () => {
    expect(isRecorderOutdated("0.2.0")).toBe(true);
    expect(isRecorderOutdated("0.10.0")).toBe(false);
  });
  test("a missing or unreadable version counts as outdated", () => {
    expect(isRecorderOutdated(null)).toBe(true);
    expect(isRecorderOutdated("")).toBe(true);
  });
});
