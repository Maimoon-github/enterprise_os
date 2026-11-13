import { test, expect } from "bun:test";
import { coerceValue, inferColumnType, normalizeMapping } from "./import";

test("0/1-only columns infer as number, not boolean", () => {
  expect(inferColumnType(["0", "1", "1"])).toBe("number");
  expect(inferColumnType(["true", "false"])).toBe("boolean");
  expect(inferColumnType(["yes", "no", "1"])).toBe("boolean");
  expect(inferColumnType(["1", "2", "3"])).toBe("number");
});

test("values that fail coercion are kept as raw strings", () => {
  expect(coerceValue("1,200", "number")).toBe(1200);
  expect(coerceValue("N/A", "number")).toBe("N/A");
  expect(coerceValue("maybe", "boolean")).toBe("maybe");
  expect(coerceValue("Yes", "boolean")).toBe(true);
  expect(coerceValue("no", "boolean")).toBe(false);
  expect(coerceValue("", "number")).toBeNull();
  expect(coerceValue("{bad", "json")).toBe("{bad");
  expect(coerceValue("a;b", "multiselect")).toEqual(["a", "b"]);
});

test("normalizeMapping validates entries and defaults the name to the header", () => {
  const headers = ["Name", "Age"];
  const keys = new Set(["name"]);
  const ok = normalizeMapping(
    [{ headerIndex: 0, action: "map", columnKey: "name" }, { headerIndex: 1, action: "create", type: "number" }],
    headers,
    keys,
  );
  expect(ok).toEqual({
    ok: true,
    mapping: [
      { headerIndex: 0, action: "map", columnKey: "name" },
      { headerIndex: 1, action: "create", name: "Age", type: "number" },
    ],
  });

  const bad = (m: unknown) => normalizeMapping(m, headers, keys).ok;
  expect(bad({})).toBe(false);
  expect(bad([{ headerIndex: 0, action: "create", name: "X", type: "formula" }])).toBe(false);
  expect(bad([{ headerIndex: 0, action: "create", name: "X", type: "nope" }])).toBe(false);
  expect(bad([{ headerIndex: 0, action: "create", name: 5, type: "text" }])).toBe(false);
  expect(bad([{ headerIndex: 9, action: "skip" }])).toBe(false);
  expect(bad([{ headerIndex: 0.5, action: "skip" }])).toBe(false);
  expect(bad([{ headerIndex: "0", action: "skip" }])).toBe(false);
  expect(bad([{ headerIndex: 0, action: "map", columnKey: "ghost" }])).toBe(false);
  expect(bad([{ headerIndex: 0, action: "skip" }, { headerIndex: 0, action: "skip" }])).toBe(false);
  expect(bad([{ headerIndex: 0, action: "explode" }])).toBe(false);
  expect(bad([null])).toBe(false);
});
