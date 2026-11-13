import { describe, expect, test } from "bun:test";
import { resolveTimeZone } from "./timeZone";

describe("resolveTimeZone", () => {
  test("maps ICU's legacy ids to the current IANA name", () => {
    expect(resolveTimeZone("Asia/Calcutta")).toBe("Asia/Kolkata");
    expect(resolveTimeZone("Europe/Kiev")).toBe("Europe/Kyiv");
    expect(resolveTimeZone("Asia/Saigon")).toBe("Asia/Ho_Chi_Minh");
  });

  test("keeps current names and falls back to UTC", () => {
    expect(resolveTimeZone("Asia/Kolkata")).toBe("Asia/Kolkata");
    expect(resolveTimeZone("America/New_York")).toBe("America/New_York");
    expect(resolveTimeZone("Not/A_Zone")).toBe("UTC");
    expect(resolveTimeZone(null)).toBe("UTC");
  });
});
