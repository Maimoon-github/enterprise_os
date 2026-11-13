import { describe, expect, test } from "bun:test";
import * as XLSX from "xlsx";
import { coerceClipboardValue, parseNumericText } from "./clipboard";
import { inferColumnType, looksLikeDate, parseSpreadsheet } from "./import";
import { describeAcceptedInputTypes, inputAcceptsColumnType } from "./value-types";
import { findOutputInResponse } from "./enrichments";
import { assertFormulaSyntax, excelOnlyOperator } from "./runners/formula";
import { bracketProblem } from "./runners/sandbox";

describe("currency and number coercion", () => {
  test("strips symbols, codes, separators and reads accounting negatives", () => {
    expect(coerceClipboardValue("$1,234.5", "currency")).toBe(1234.5);
    expect(coerceClipboardValue("€ 99", "currency")).toBe(99);
    expect(coerceClipboardValue("£1,000", "number")).toBe(1000);
    expect(coerceClipboardValue("USD 12.50", "currency")).toBe(12.5);
    expect(coerceClipboardValue("12 USD", "currency")).toBe(12);
    expect(coerceClipboardValue("(1,200)", "number")).toBe(-1200);
    expect(coerceClipboardValue("-$5", "currency")).toBe(-5);
    expect(coerceClipboardValue("  ₹ 1,00,000 ", "currency")).toBe(100000);
  });
  test("keeps what is not a number as typed", () => {
    expect(coerceClipboardValue("N/A", "number")).toBe("N/A");
    expect(coerceClipboardValue("50%", "number")).toBe("50%");
    expect(coerceClipboardValue("12abc", "currency")).toBe("12abc");
    expect(parseNumericText("0x10")).toBeNull();
    expect(parseNumericText("Infinity")).toBeNull();
    expect(parseNumericText("1e3")).toBe(1000);
  });
});

describe("import type inference", () => {
  test("dates need a real date shape", () => {
    expect(inferColumnType(["a&b=1"])).toBe("text");
    expect(inferColumnType(["Room 5", "Suite 12"])).toBe("text");
    expect(inferColumnType(["2024-01-05", "2024-02-10 13:45", "2024-03-01T10:00:00Z"])).toBe("date");
    expect(inferColumnType(["05/01/2024", "13/02/2024"])).toBe("date");
    expect(inferColumnType(["Jan 5, 2024", "5 Feb 2024"])).toBe("date");
    expect(looksLikeDate("99/99/2024")).toBe(false);
    expect(looksLikeDate("x=2024-01-05")).toBe(false);
  });
  test("numbers tolerate a stray non-numeric value", () => {
    const column = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"];
    expect(inferColumnType([...column, "N/A"])).toBe("number"); // 10 of 11
    expect(inferColumnType([...column.slice(0, 8), "N/A"])).toBe("text"); // 8 of 9 is under 90%
  });
  test("90% numeric is a number column, formatted text included", () => {
    const column = Array.from({ length: 19 }, (_, i) => String(i + 2));
    expect(inferColumnType([...column, "N/A"])).toBe("number");
    expect(inferColumnType(["$1,200", "$3,400.50", "(500)"])).toBe("number");
    expect(inferColumnType(["1.2e+21", "5"])).toBe("number");
    expect(inferColumnType(["02134", "90210"])).toBe("text");
    expect(inferColumnType(["N/A", "n/a"])).toBe("text");
  });
  test("an XLSX Revenue column agrees with its CSV twin", () => {
    const build = (bookType: "xlsx" | "csv", rows: unknown[][]) => {
      const book = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(book, XLSX.utils.aoa_to_sheet(rows), "S");
      return XLSX.write(book, { type: "array", bookType }) as ArrayBuffer;
    };
    const kinds = [
      [["Revenue"], [1200], [3400.5], [1.5e21]],
      [["Revenue"], ["$1,200"], ["$3,400.50"], ["(500)"]],
    ];
    for (const rows of kinds) {
      const parsed = [parseSpreadsheet(build("xlsx", rows)), parseSpreadsheet(build("csv", rows))];
      const types = parsed.map((p) => (p.ok ? inferColumnType(p.sheet.rows.map((r) => r[0])) : "error"));
      expect(types).toEqual(["number", "number"]);
    }
  });
});

describe("enrichment input compatibility", () => {
  test("string inputs accept every text-like column and formulas", () => {
    for (const type of ["text", "url", "email", "select", "formula"] as const) {
      expect(inputAcceptsColumnType(["url"], type)).toBe(true);
    }
    expect(inputAcceptsColumnType(["text", "url"], "email")).toBe(true);
  });
  test("incompatible types stay rejected", () => {
    for (const type of ["boolean", "json", "number", "date", "multiselect"] as const) {
      expect(inputAcceptsColumnType(["url"], type)).toBe(false);
    }
    expect(inputAcceptsColumnType(["number"], "text")).toBe(false);
    expect(inputAcceptsColumnType(["date", "text"], "date")).toBe(true);
    expect(describeAcceptedInputTypes(["url"])).toContain("text");
  });
});

describe("enrichment backfill lookup", () => {
  test("finds the shallowest field named like the output", () => {
    const response = { result: { emails: [{ email: "a@b.co", mxProvider: "google" }] } };
    expect(findOutputInResponse(response, "mxProvider")).toBe("google");
    expect(findOutputInResponse(response, "MXPROVIDER")).toBe("google");
    expect(findOutputInResponse(response, "missing")).toBeUndefined();
    expect(findOutputInResponse(null, "x")).toBeUndefined();
  });
});

describe("formula syntax", () => {
  test("reports the unclosed bracket, not the wrapper", () => {
    expect(bracketProblem('{{x}} + (')).toContain('Unclosed "("');
    expect(bracketProblem('"(" + 1')).toBeNull();
    expect(bracketProblem("1 + )")).toContain('Unexpected ")"');
  });
  test("rejects a broken expression and accepts a good one", async () => {
    await expect(assertFormulaSyntax("{{firstName}} + (")).rejects.toThrow(/Unclosed "\("/);
    await expect(assertFormulaSyntax("{{a}} +")).rejects.toThrow(/syntax/i);
    await assertFormulaSyntax('UPPER({{name}}) + "-" + {{domain}}');
  });
  test("flags Excel-only operators outside strings", () => {
    expect(excelOnlyOperator('UPPER({{a}}) & "-" & {{b}}')).toContain("+");
    expect(excelOnlyOperator("{{a}} <> 1")).toContain("!==");
    expect(excelOnlyOperator('{{a}} && "a&b"')).toBeNull();
  });
});

test("a blank text token is an empty string in a formula; a blank number stays null", async () => {
  const { substituteTokens } = await import("./runners/formula");
  const text = new Set(["first", "last"]);
  expect(substituteTokens('{{first}} + " " + {{last}}', { first: "Pat" }, text)).toBe('"Pat" + " " + ""');
  expect(substituteTokens("{{n}} * 2", { n: null }, text)).toBe("null * 2");
  expect(substituteTokens("{{first}}", { first: "" })).toBe("null");
});

test("formulas see blank text as '' and ISBLANK agrees", async () => {
  const { evaluateOnce } = await import("./runners/formula");
  const text = new Set(["first", "last"]);
  expect(await evaluateOnce('{{first}} + " " + {{last}}', { first: "Pat" }, {}, text)).toEqual({ ok: true, value: "Pat " });
  expect(await evaluateOnce("ISBLANK({{last}})", { first: "Pat" }, {}, text)).toEqual({ ok: true, value: true });
  expect(await evaluateOnce("{{n}} * 2", {}, {}, text)).toEqual({ ok: true, value: 0 });
});
