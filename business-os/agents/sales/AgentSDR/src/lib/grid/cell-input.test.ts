import { expect, test } from "bun:test";
import { coerceCellInput } from "./cell-input";

test("numbers", () => {
  expect(coerceCellInput("1,200", "number")).toEqual({ ok: true, value: 1200 });
  expect(coerceCellInput("N/A", "number")).toEqual({ ok: true, value: "N/A" });
  expect(coerceCellInput({ a: 1 }, "number").ok).toBe(false);
  expect(coerceCellInput("", "currency")).toEqual({ ok: true, value: null });
});

test("booleans and dates", () => {
  expect(coerceCellInput("yes", "boolean")).toEqual({ ok: true, value: true });
  expect(coerceCellInput("maybe", "boolean")).toEqual({ ok: true, value: "maybe" });
  expect(coerceCellInput("2026-01-05", "date")).toEqual({ ok: true, value: "2026-01-05" });
  expect(coerceCellInput("not a date", "date")).toEqual({ ok: true, value: "not a date" });
});

test("json and text", () => {
  expect(coerceCellInput('{"a":1}', "json")).toEqual({ ok: true, value: { a: 1 } });
  expect(coerceCellInput("{oops", "json")).toEqual({ ok: true, value: "{oops" });
  expect(coerceCellInput({ a: 1 }, "json")).toEqual({ ok: true, value: { a: 1 } });
  expect(coerceCellInput("hi\u0000", "text")).toEqual({ ok: true, value: "hi" });
  expect(coerceCellInput(5, "email")).toEqual({ ok: true, value: "5" });
});
