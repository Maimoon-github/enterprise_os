import { describe, expect, test } from "bun:test";
import { formatCallDuration, formatElapsed, formatOffset } from "./formatElapsed";

describe("formatElapsed", () => {
  test("formats whole minutes and seconds as m:ss", () => {
    expect(formatElapsed(0)).toBe("0:00");
    expect(formatElapsed(5_000)).toBe("0:05");
    expect(formatElapsed(65_000)).toBe("1:05");
    expect(formatElapsed(600_000)).toBe("10:00");
  });

  test("rounds down to the last full second", () => {
    expect(formatElapsed(1_999)).toBe("0:01");
  });

  test("never goes negative, e.g. before the first tick catches up to answeredAt", () => {
    expect(formatElapsed(-500)).toBe("0:00");
  });
});

describe("formatCallDuration", () => {
  test("rounds to the nearest second, and is null when unknown", () => {
    expect(formatCallDuration(14_600)).toBe("0:15");
    expect(formatCallDuration(222_000)).toBe("3:42");
    expect(formatCallDuration(null)).toBeNull();
  });
});

describe("formatOffset", () => {
  test("formats a transcript offset in seconds", () => {
    expect(formatOffset(83.4)).toBe("1:23");
    expect(formatOffset(-2)).toBe("0:00");
  });
});
