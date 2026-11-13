import { expect, test } from "bun:test";
import { isTransientOpenRouterError } from "./openrouter-errors";

const withStatus = (status: number) => Object.assign(new Error("x"), { status });

test("429, 5xx and 408 are retried", () => {
  for (const status of [429, 500, 502, 503, 408]) expect(isTransientOpenRouterError(withStatus(status))).toBe(true);
});

test("other 4xx are permanent", () => {
  for (const status of [400, 401, 402, 403, 404]) expect(isTransientOpenRouterError(withStatus(status))).toBe(false);
});

test("status is found through the cause chain", () => {
  expect(isTransientOpenRouterError(new Error("failed", { cause: withStatus(429) }))).toBe(true);
});

test("unreachable provider is retried; timeouts (maybe billed) and config errors are not", () => {
  expect(isTransientOpenRouterError(Object.assign(new Error("The operation was aborted"), { name: "AbortError" }))).toBe(false);
  expect(isTransientOpenRouterError(new Error("Request timed out."))).toBe(false);
  expect(isTransientOpenRouterError(new Error("fetch failed"))).toBe(true);
  expect(isTransientOpenRouterError(new Error("Connect OpenRouter in AI Settings"))).toBe(false);
  expect(isTransientOpenRouterError("nope")).toBe(false);
});
