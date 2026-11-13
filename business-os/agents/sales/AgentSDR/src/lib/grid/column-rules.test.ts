import { test, expect } from "bun:test";
import { convertStoredValue, uniqueColumnName, validateColumnConfig } from "./columns";
import { pairOutputsWithColumns } from "./ai-columns";
import { isBlankLookupKey } from "./formula-lookups";

test("uniqueColumnName suffixes case-insensitively", () => {
  expect(uniqueColumnName("Text", [])).toBe("Text");
  expect(uniqueColumnName("Text", ["Text"])).toBe("Text 2");
  expect(uniqueColumnName("text", ["Text"])).toBe("text 2");
  expect(uniqueColumnName("Text", ["TEXT", "Text 2"])).toBe("Text 3");
  expect(uniqueColumnName("  Company ", ["company"])).toBe("Company 2");
});

test("convertStoredValue converts like a paste and keeps what cannot convert", () => {
  expect(convertStoredValue("1,200", "number")).toBe(1200);
  expect(convertStoredValue("N/A", "number")).toBe("N/A");
  expect(convertStoredValue("yes", "boolean")).toBe(true);
  expect(convertStoredValue("maybe", "boolean")).toBe("maybe");
  expect(convertStoredValue(1200, "text")).toBe("1200");
  expect(convertStoredValue(1, "boolean")).toBe(true);
  expect(convertStoredValue(["a", "b"], "text")).toBe("a, b");
  expect(convertStoredValue("a; b", "multiselect")).toEqual(["a", "b"]);
  expect(convertStoredValue(null, "number")).toBeNull();
  expect(convertStoredValue("", "number")).toBeNull();
});

test("static column config validation", () => {
  expect(() => validateColumnConfig("select", { options: ["a", "b"] } as never)).not.toThrow();
  expect(() => validateColumnConfig("select", { options: [{ value: "a", label: "A" }] } as never)).not.toThrow();
  expect(() => validateColumnConfig("multiselect", { options: "a,b" } as never)).toThrow();
  expect(() => validateColumnConfig("select", { options: [1, 2] } as never)).toThrow();
  expect(() => validateColumnConfig("currency", { currency: 5 } as never)).toThrow();
  expect(() => validateColumnConfig("currency", { currency: "USD" })).not.toThrow();
  expect(() => validateColumnConfig("text", [] as never)).toThrow();
  expect(() => validateColumnConfig("text", null as never)).toThrow();
});

test("an HTTP column may only name a GRID_HTTP_SECRET_ env var", () => {
  const base = { method: "GET", url: "https://api.test" } as const;
  expect(() => validateColumnConfig("http", { ...base, authEnvVar: "DATABASE_URL" })).toThrow(/GRID_HTTP_SECRET_/);
  expect(() => validateColumnConfig("http", { ...base, authEnvVar: "GRID_HTTP_SECRET_APOLLO" })).not.toThrow();
  expect(() => validateColumnConfig("http", { ...base })).not.toThrow();
});

const fields = (...pairs: [string, string, string][]) =>
  pairs.map(([key, name, type]) => ({ key, name, type })) as never[];
const owned = (...pairs: [string, string][]) => pairs.map(([key, name]) => ({ key, name }));

test("AI outputs reuse only the column's own output columns", () => {
  // "Email" exists as the user's static column, but is NOT an output of this AI column.
  const paired = pairOutputsWithColumns(
    fields(["email", "Email", "email"]),
    [],
    {},
    owned(),
  );
  expect(paired.size).toBe(0);
});

test("AI outputs keep their column by field key; a new key is a new field", () => {
  const previousFields = fields(["a", "Alpha", "text"], ["b", "Beta", "number"]);
  const mapping = { a: "alpha", b: "beta" };
  const own = owned(["alpha", "Alpha"], ["beta", "Beta"]);

  // Same keys, one renamed: the dialog keeps a saved field's key.
  expect(Object.fromEntries(pairOutputsWithColumns(fields(["a", "Renamed", "text"], ["b", "Beta", "number"]), previousFields, mapping, own))).toEqual({ a: "alpha", b: "beta" });

  // [A, B] -> [B, C]: C is new, and must not inherit A's column and data.
  expect(
    Object.fromEntries(pairOutputsWithColumns(fields(["b", "Beta", "number"], ["c", "Gamma", "text"]), previousFields, mapping, own)),
  ).toEqual({ b: "beta" });
});

test("AI output with the same name as an owned column is matched by name", () => {
  const paired = pairOutputsWithColumns(fields(["new", "Summary", "text"]), [], {}, owned(["summary", "Summary"]));
  expect(paired.get("new")).toBe("summary");
});

test("blank lookup keys", () => {
  for (const v of [null, undefined, "", "  "]) expect(isBlankLookupKey(v)).toBe(true);
  for (const v of [0, "a", false]) expect(isBlankLookupKey(v)).toBe(false);
});

test("convertStoredValue never flattens objects to [object Object]", () => {
  expect(convertStoredValue([{ a: 1 }], "text")).toBe('[{"a":1}]');
  expect(convertStoredValue({ a: 1 }, "text")).toBe('{"a":1}');
});
