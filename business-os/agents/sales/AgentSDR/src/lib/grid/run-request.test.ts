import { expect, test } from "bun:test";
import { parseRunRequest } from "./run-request";

const ID = "3f2b8c1e-9d4a-4b7e-8a11-2c5d6e7f8091";

test("empty body runs everything", () => {
  expect(parseRunRequest("")).toEqual({ ok: true, value: {} });
});

test("malformed JSON is rejected", () => {
  expect(parseRunRequest("{oops").ok).toBe(false);
  expect(parseRunRequest("[1]").ok).toBe(false);
});

test("an empty rowIds array is preserved, not widened", () => {
  const parsed = parseRunRequest('{"columnKey":"a","rowIds":[]}');
  expect(parsed).toEqual({ ok: true, value: { columnKey: "a", rowIds: [], onlyEmpty: undefined } });
});

test("rowIds must be uuids", () => {
  expect(parseRunRequest(JSON.stringify({ rowIds: [ID] })).ok).toBe(true);
  expect(parseRunRequest(JSON.stringify({ rowIds: ["nope"] })).ok).toBe(false);
  expect(parseRunRequest(JSON.stringify({ rowIds: "x" })).ok).toBe(false);
});
