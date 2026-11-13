import { describe, expect, test } from "bun:test";
import { normalizePhone, whatsappDigits } from "./phone";

describe("normalizePhone", () => {
  test("accepts a valid Indian number given with a country code", () => {
    expect(normalizePhone("+91 98765 43210")).toBe("+919876543210");
  });

  test("accepts a valid US number given with dashes", () => {
    expect(normalizePhone("+1-415-555-2671")).toBe("+14155552671");
  });

  test("accepts a valid UK number given with parentheses and spacing", () => {
    expect(normalizePhone("+44 20 7946 0958")).toBe("+442079460958");
  });

  test("accepts messy spacing and dashes around a country code", () => {
    expect(normalizePhone("+91 98765-43210")).toBe("+919876543210");
  });

  test("accepts a leading-00 international prefix when it matches the default country's IDD", () => {
    expect(normalizePhone("0091 98765 43210", "IN")).toBe("+919876543210");
  });

  test("parses a number given without '+' when a default country is set", () => {
    expect(normalizePhone("98765 43210", "IN")).toBe("+919876543210");
  });

  test("returns null for a number given without '+' and no default country", () => {
    expect(normalizePhone("98765 43210")).toBeNull();
  });

  test("returns null for garbage input", () => {
    expect(normalizePhone("not a phone number")).toBeNull();
  });

  test("returns null for an empty or blank string", () => {
    expect(normalizePhone("")).toBeNull();
    expect(normalizePhone("   ")).toBeNull();
  });

  test("returns null for a string that is too short to be valid", () => {
    expect(normalizePhone("+91 123")).toBeNull();
  });
});

describe("whatsappDigits", () => {
  test("strips the leading '+' and keeps only digits", () => {
    expect(whatsappDigits("+919876543210")).toBe("919876543210");
  });

  test("strips any stray non-digit characters", () => {
    expect(whatsappDigits("+1 (415) 555-2671")).toBe("14155552671");
  });
});
