import { test, expect } from "bun:test";
import { clientMessage, intParam, isUuid, nullableUuid, optionalName, requireString } from "./validate";

test("isUuid accepts UUIDs only", () => {
  expect(isUuid("3f2b8c1e-5d4a-4e6f-9a1b-0c2d3e4f5a6b")).toBe(true);
  expect(isUuid("xyz")).toBe(false);
  expect(isUuid("")).toBe(false);
  expect(isUuid(undefined)).toBe(false);
  expect(isUuid(42)).toBe(false);
});

test("requireString trims, rejects blank, non-text and over-long names", () => {
  expect(requireString("  Leads ", "name")).toEqual({ ok: true, value: "Leads" });
  expect(requireString("   ", "name").ok).toBe(false);
  expect(requireString("", "name").ok).toBe(false);
  expect(requireString(5, "name").ok).toBe(false);
  expect(requireString("x".repeat(201), "name").ok).toBe(false);
  expect(requireString("x".repeat(200), "name").ok).toBe(true);
});

test("optionalName: absent passes, blank is rejected unless blankMeansDefault", () => {
  expect(optionalName(undefined)).toEqual({ ok: true, value: undefined });
  expect(optionalName("").ok).toBe(false);
  expect(optionalName("", "name", true)).toEqual({ ok: true, value: undefined });
  expect(optionalName(7, "name", true).ok).toBe(false);
});

test("nullableUuid allows null and absent, rejects junk", () => {
  expect(nullableUuid(undefined, "folderId")).toEqual({ ok: true, value: undefined });
  expect(nullableUuid(null, "folderId")).toEqual({ ok: true, value: null });
  expect(nullableUuid("nope", "folderId").ok).toBe(false);
});

test("intParam: fallback when absent, null when malformed or out of range", () => {
  expect(intParam(null, 200)).toBe(200);
  expect(intParam("50", 200)).toBe(50);
  expect(intParam("abc", 200)).toBeNull();
  expect(intParam("-1", 200)).toBeNull();
  expect(intParam("1.5", 200)).toBeNull();
  expect(intParam("5000", 200, { max: 1000 })).toBeNull();
  expect(intParam("0", 200, { min: 1 })).toBeNull();
});

test("clientMessage hides database errors but keeps validation messages", () => {
  expect(clientMessage(new Error("Column is used by: A"), "fallback")).toBe("Column is used by: A");
  expect(clientMessage(new Error('Failed query: select * from x params: y'), "fallback")).toBe("fallback");
  expect(clientMessage(Object.assign(new Error('invalid input syntax for type uuid: "xyz"'), { code: "22P02" }), "fallback")).toBe("fallback");
  expect(clientMessage("boom", "fallback")).toBe("fallback");
});
