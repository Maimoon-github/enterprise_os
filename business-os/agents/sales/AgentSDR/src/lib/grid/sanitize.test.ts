import { expect, test } from "bun:test";
import { cleanJson, cleanString } from "./sanitize";

test("strips NUL and replaces lone surrogates", () => {
  expect(cleanString("a\u0000b")).toBe("ab");
  expect(cleanString("x\uD800y")).toBe("x�y");
  expect(cleanString("x\uDC00y")).toBe("x�y");
  expect(cleanString("ok 😀")).toBe("ok 😀");
});

test("cleans nested values and keys", () => {
  expect(cleanJson<unknown>({ "k\u0000": ["a\u0000", { n: 1, s: "\uD800" }], d: null })).toEqual({
    k: ["a", { n: 1, s: "�" }],
    d: null,
  });
});
