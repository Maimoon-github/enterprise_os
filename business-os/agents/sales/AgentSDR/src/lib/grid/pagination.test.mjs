import { describe, expect, test } from "bun:test";
import { clampGridPage, gridPageCount, gridPageRange } from "./pagination.ts";

describe("grid pagination", () => {
  test("splits a large import into stable 200-row pages", () => {
    expect(gridPageCount(450)).toBe(3);
    expect(gridPageRange(0, 450)).toEqual({ start: 1, end: 200 });
    expect(gridPageRange(1, 450)).toEqual({ start: 201, end: 400 });
    expect(gridPageRange(2, 450)).toEqual({ start: 401, end: 450 });
  });

  test("clamps pages after rows are deleted", () => {
    expect(clampGridPage(9, 201)).toBe(1);
    expect(clampGridPage(-2, 201)).toBe(0);
    expect(clampGridPage(Number.NaN, 201)).toBe(0);
    expect(gridPageRange(0, 0)).toEqual({ start: 0, end: 0 });
  });
});
