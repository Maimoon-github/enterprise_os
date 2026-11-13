import { test, expect } from "bun:test";
import { assertKnownColumns, escapeLike, sanitizeView, validateView, type GridQuery } from "./query";

const known = new Set(["name", "email"]);

test("escapeLike neutralises LIKE wildcards and the escape character", () => {
  expect(escapeLike("50%")).toBe("50\\%");
  expect(escapeLike("a_b")).toBe("a\\_b");
  expect(escapeLike("c:\\dir")).toBe("c:\\\\dir");
  expect(escapeLike("plain")).toBe("plain");
  expect(escapeLike("%")).toBe("\\%");
});

test("sanitizeView drops sorts and filters the table cannot apply", () => {
  const view = sanitizeView(
    {
      hiddenColumns: ["name", "gone"],
      sorts: [
        { columnKey: "name", direction: "sideways" },
        { columnKey: "gone", direction: "asc" },
        { columnKey: "email", direction: "desc" },
        "junk",
      ],
      filters: {
        conjunction: "bogus",
        conditions: [
          { columnKey: "name", operator: "eq", value: "x" },
          { columnKey: "gone", operator: "eq", value: "x" },
          { columnKey: "name", operator: "regex", value: "x" },
          { conjunction: "or", conditions: [{ columnKey: "email", operator: "empty" }, { columnKey: "gone", operator: "empty" }] },
          null,
        ],
      },
    },
    known,
  );
  expect(view.hiddenColumns).toEqual(["name"]);
  expect(view.sorts).toEqual([{ columnKey: "email", direction: "desc" }]);
  expect(view.filters).toEqual({
    conjunction: "and",
    conditions: [
      { columnKey: "name", operator: "eq", value: "x" },
      { conjunction: "or", conditions: [{ columnKey: "email", operator: "empty" }] },
    ],
  });
});

test("sanitizeView of a non-object is an empty view", () => {
  expect(sanitizeView(null, known)).toEqual({});
  expect(sanitizeView("x", known)).toEqual({});
});

test("assertKnownColumns prunes in place instead of throwing", () => {
  const query: GridQuery = {
    sorts: [{ columnKey: "gone", direction: "asc" }],
    filters: { conjunction: "and", conditions: [{ columnKey: "gone", operator: "eq", value: "1" }] },
  };
  expect(() => assertKnownColumns(query, known)).not.toThrow();
  expect(query.sorts).toEqual([]);
  expect(query.filters?.conditions).toEqual([]);
});

test("validateView rejects bad direction, operator, unknown column and bad shape", () => {
  expect(validateView({ sorts: [{ columnKey: "name", direction: "sideways" }] }, known)).toContain("asc or desc");
  expect(validateView({ sorts: [{ columnKey: "gone", direction: "asc" }] }, known)).toContain("gone");
  expect(
    validateView({ filters: { conjunction: "and", conditions: [{ columnKey: "name", operator: "nope" }] } }, known),
  ).toContain("operator");
  expect(
    validateView({ filters: { conjunction: "and", conditions: [{ columnKey: "gone", operator: "eq" }] } }, known),
  ).toContain("gone");
  expect(validateView({ filters: { conjunction: "xor", conditions: [] } }, known)).toContain("conjunction");
  expect(validateView([], known)).not.toBeNull();
  expect(validateView({ sorts: "name" }, known)).not.toBeNull();
  expect(validateView({ hiddenColumns: [1] }, known)).not.toBeNull();
});

test("validateView accepts a well-formed view", () => {
  expect(
    validateView(
      {
        hiddenColumns: ["email"],
        sorts: [{ columnKey: "name", direction: "asc" }],
        filters: { conjunction: "or", conditions: [{ columnKey: "name", operator: "contains", value: "a" }] },
      },
      known,
    ),
  ).toBeNull();
  expect(validateView({}, known)).toBeNull();
});
