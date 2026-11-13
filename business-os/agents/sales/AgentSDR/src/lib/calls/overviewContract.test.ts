import { describe, expect, test } from "bun:test";
import { average, isDateString, listDays, rate } from "./overviewContract";
import { formatDuration, formatRate, presetRange } from "./overviewFormat";

describe("listDays", () => {
  test("is inclusive and zero-filled", () => {
    expect(listDays("2026-09-28", "2026-10-02")).toEqual(["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02"]);
  });
  test("a single day", () => {
    expect(listDays("2026-09-30", "2026-09-30")).toEqual(["2026-09-30"]);
  });
  test("crosses a leap day", () => {
    expect(listDays("2028-02-28", "2028-03-01")).toEqual(["2028-02-28", "2028-02-29", "2028-03-01"]);
  });
  test("empty for reversed or invalid input", () => {
    expect(listDays("2026-10-02", "2026-09-28")).toEqual([]);
    expect(listDays("nope", "2026-09-28")).toEqual([]);
  });
});

describe("isDateString", () => {
  test("accepts real dates only", () => {
    expect(isDateString("2026-02-28")).toBe(true);
    expect(isDateString("2026-02-30")).toBe(false);
    expect(isDateString("2026-2-3")).toBe(false);
    expect(isDateString("")).toBe(false);
  });
});

describe("rate math", () => {
  test("rate is null on a zero denominator", () => {
    expect(rate(0, 0)).toBeNull();
    expect(rate(1, 4)).toBe(0.25);
  });
  test("average rounds and is null on zero", () => {
    expect(average(100, 0)).toBeNull();
    expect(average(100, 3)).toBe(33);
  });
});

describe("display helpers", () => {
  test("formatDuration", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(38_000)).toBe("38s");
    expect(formatDuration(252_000)).toBe("4m 12s");
    expect(formatDuration(3_900_000)).toBe("1h 05m");
  });
  test("formatRate", () => {
    expect(formatRate(null)).toBe("—");
    expect(formatRate(0.4255)).toBe("42.5%");
  });
  test("presetRange ends today and spans n days", () => {
    const now = new Date(2026, 8, 30, 15, 0);
    expect(presetRange(1, now)).toEqual({ from: "2026-09-30", to: "2026-09-30" });
    expect(presetRange(7, now)).toEqual({ from: "2026-09-24", to: "2026-09-30" });
  });
});
