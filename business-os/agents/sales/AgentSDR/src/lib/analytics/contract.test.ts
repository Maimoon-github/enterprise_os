import { describe, expect, test } from "bun:test";
import { bucketFor, bucketStarts, change, previousRange, ratio, toSeries } from "./contract";

describe("previousRange", () => {
  test("is the equally long range ending the day before", () => {
    expect(previousRange({ from: "2026-09-08", to: "2026-09-14" })).toEqual({ from: "2026-09-01", to: "2026-09-07" });
  });
  test("a single day", () => {
    expect(previousRange({ from: "2026-03-01", to: "2026-03-01" })).toEqual({ from: "2026-02-28", to: "2026-02-28" });
  });
  test("crosses a year boundary", () => {
    expect(previousRange({ from: "2026-01-01", to: "2026-01-10" })).toEqual({ from: "2025-12-22", to: "2025-12-31" });
  });
});

describe("bucketStarts", () => {
  test("day buckets are every day, inclusive", () => {
    expect(bucketStarts({ from: "2026-09-01", to: "2026-09-04", bucket: "day" })).toEqual([
      "2026-09-01",
      "2026-09-02",
      "2026-09-03",
      "2026-09-04",
    ]);
  });
  test("week buckets start on the range's first day", () => {
    expect(bucketStarts({ from: "2026-09-01", to: "2026-09-20", bucket: "week" })).toEqual([
      "2026-09-01",
      "2026-09-08",
      "2026-09-15",
    ]);
  });
});

describe("bucketFor", () => {
  const week = { from: "2026-09-01", bucket: "week" as const };
  test("day bucket is the day itself", () => {
    expect(bucketFor("2026-09-05", { from: "2026-09-01", bucket: "day" })).toBe("2026-09-05");
  });
  test("week bucket boundaries", () => {
    expect(bucketFor("2026-09-01", week)).toBe("2026-09-01");
    expect(bucketFor("2026-09-07", week)).toBe("2026-09-01");
    expect(bucketFor("2026-09-08", week)).toBe("2026-09-08");
    expect(bucketFor("2026-09-16", week)).toBe("2026-09-15");
  });
});

describe("toSeries", () => {
  const keys = ["a", "b"] as const;
  test("zero-fills days with no rows", () => {
    const s = toSeries(keys, { from: "2026-09-01", to: "2026-09-03", bucket: "day" }, [{ date: "2026-09-02", a: 4 }]);
    expect(s.keys).toEqual(keys);
    expect(s.points).toEqual([
      { date: "2026-09-01", a: 0, b: 0 },
      { date: "2026-09-02", a: 4, b: 0 },
      { date: "2026-09-03", a: 0, b: 0 },
    ]);
  });
  test("sums days into weekly buckets", () => {
    const s = toSeries(keys, { from: "2026-09-01", to: "2026-09-14", bucket: "week" }, [
      { date: "2026-09-01", a: 1, b: 2 },
      { date: "2026-09-07", a: 3 },
      { date: "2026-09-08", b: 5 },
      { date: "2026-09-14", a: 1 },
    ]);
    expect(s.points).toEqual([
      { date: "2026-09-01", a: 4, b: 2 },
      { date: "2026-09-08", a: 1, b: 5 },
    ]);
  });
  test("ignores rows outside the range", () => {
    const s = toSeries(keys, { from: "2026-09-02", to: "2026-09-03", bucket: "day" }, [
      { date: "2026-09-01", a: 9 },
      { date: "2026-09-04", a: 9 },
      { date: "2026-09-03", a: 1 },
    ]);
    expect(s.points.map((p) => p.a)).toEqual([0, 1]);
  });
});

describe("ratio and change", () => {
  test("ratio is null on a zero denominator", () => {
    expect(ratio(1, 0)).toBeNull();
    expect(ratio(0, 0)).toBeNull();
    expect(ratio(1, 4)).toBe(0.25);
    expect(ratio(0, 5)).toBe(0);
  });
  test("change is a fraction, null without a base", () => {
    expect(change(150, 100)).toBe(0.5);
    expect(change(50, 100)).toBe(-0.5);
    expect(change(5, 0)).toBeNull();
    expect(change(null, 3)).toBeNull();
    expect(change(3, null)).toBeNull();
  });
});
