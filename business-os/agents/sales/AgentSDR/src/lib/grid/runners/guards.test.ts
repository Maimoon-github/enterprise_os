import { expect, test } from "bun:test";
import { allReferencedInputsEmpty, columnDelaySeconds, columnRunCondition } from "./guards";
import { aiProviderLabel, interpolate, ownCell } from "./types";

const ai = (prompt: string) => ({ type: "ai" as const, config: { prompt } });

test("skips only when every referenced token is empty", () => {
  expect(allReferencedInputsEmpty(ai("Hi {{a}} {{b}}"), { a: "", b: null })).toBe(true);
  expect(allReferencedInputsEmpty(ai("Hi {{a}} {{b}}"), { a: "x" })).toBe(false);
  expect(allReferencedInputsEmpty(ai("no tokens"), {})).toBe(false);
  expect(allReferencedInputsEmpty(ai("{{a}}"), { a: [] })).toBe(true);
});

test("formula and http tokens", () => {
  // Formulas are free and may be written for blanks: never skipped.
  expect(allReferencedInputsEmpty({ type: "formula", config: { expression: "{{employees}} * 2" } }, {})).toBe(false);
  expect(allReferencedInputsEmpty({ type: "formula", config: { expression: "{{employees}} * 2" } }, { employees: 0 })).toBe(false);
  const http = { type: "http" as const, config: { method: "GET", url: "https://x/{{a}}", headers: { h: "{{b}}" } } };
  expect(allReferencedInputsEmpty(http, { a: " " })).toBe(true);
  expect(allReferencedInputsEmpty(http, { b: "z" })).toBe(false);
});

test("delay and condition", () => {
  expect(columnDelaySeconds({ type: "ai", config: { delaySeconds: 5 } })).toBe(5);
  expect(columnDelaySeconds({ type: "formula", config: { delaySeconds: 5 } })).toBe(0);
  expect(columnRunCondition({ type: "enrichment", config: { runCondition: " {{a}} > 1 " } })).toBe("{{a}} > 1");
});

test("inherited properties are not cell values", () => {
  expect(ownCell({}, "constructor")).toBeUndefined();
  expect(interpolate("[{{constructor}}][{{toString}}]", {})).toBe("[][]");
  expect(interpolate("{{a}}", { a: 1 })).toBe("1");
});

test("provider label is not doubled", () => {
  expect(aiProviderLabel("openrouter", "minimax", "minimax/minimax-m3")).toBe("openrouter/minimax/minimax-m3");
  expect(aiProviderLabel("openrouter", "deepinfra", "meta/llama")).toBe("openrouter/meta/llama@deepinfra");
});
