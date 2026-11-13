import { describe, expect, test } from "bun:test";
import { draftNow, usableSenderName } from "./draftSender";

describe("draft sender name", () => {
  test("keeps a person's name and drops phone numbers and addresses", () => {
    expect(usableSenderName("  Abha   Arora ")).toBe("Abha Arora");
    expect(usableSenderName("918076927945")).toBeNull();
    expect(usableSenderName("+91 80769 27945")).toBeNull();
    expect(usableSenderName("roy@talktokandid.com")).toBeNull();
    expect(usableSenderName("")).toBeNull();
    expect(usableSenderName(null)).toBeNull();
  });
});

describe("draft now", () => {
  test("reads the moment in the organization's time zone", () => {
    const now = draftNow(new Date("2026-10-29T04:30:00.000Z"), "Asia/Kolkata");
    expect(now.iso).toBe("2026-10-29T04:30:00.000Z");
    expect(now.timeZone).toBe("Asia/Kolkata");
    expect(now.local).toContain("Thursday");
    expect(now.local).toContain("10:00");
  });

  test("an unknown time zone falls back to UTC", () => {
    expect(draftNow(new Date("2026-10-29T04:30:00.000Z"), "Not/AZone").timeZone).toBe("UTC");
  });
});
