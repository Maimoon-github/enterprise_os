import { describe, expect, test } from "bun:test";

import {
  coerceClipboardValue,
  parseClipboardText,
  serializeClipboardGrid,
} from "./clipboard.ts";

describe("grid clipboard serialization", () => {
  test("serializes primitive and structured values as spreadsheet TSV", () => {
    const text = serializeClipboardGrid([
      ["Ada", 42, true, null, { role: "engineer" }, ["math", "code"]],
    ]);

    expect(text).toBe('Ada\t42\ttrue\t\t"{""role"":""engineer""}"\t"[""math"",""code""]"');
    expect(parseClipboardText(text)).toEqual([
      ["Ada", "42", "true", "", '{"role":"engineer"}', '["math","code"]'],
    ]);
  });

  test("quotes tabs, line breaks, and quotes without changing the grid shape", () => {
    const rows = [["a\tb", "two\nlines", 'say "hello"'], ["plain", "", "last"]];
    const text = serializeClipboardGrid(rows);

    expect(text).toBe('"a\tb"\t"two\nlines"\t"say ""hello"""\nplain\t\tlast');
    expect(parseClipboardText(text)).toEqual(rows);
  });

  test("round-trips a single cell containing a comma", () => {
    const text = serializeClipboardGrid([["Acme, Inc"]]);

    expect(text).toBe('"Acme, Inc"');
    expect(parseClipboardText(text)).toEqual([["Acme, Inc"]]);
  });

  test("can neutralize formula-like strings for external spreadsheet paste", () => {
    expect(serializeClipboardGrid([["=cmd()", "+SUM(A1:A2)", -42]], { escapeFormulas: true }))
      .toBe("'=cmd()\t'+SUM(A1:A2)\t-42");
  });
});

describe("grid clipboard parsing", () => {
  test("prefers TSV and handles CRLF, escaped quotes, and embedded newlines", () => {
    expect(parseClipboardText('Name\tNotes\r\nAda\t"first\r\nsecond"\r\nGrace\t"said ""hi"""\r\n')).toEqual([
      ["Name", "Notes"],
      ["Ada", "first\nsecond"],
      ["Grace", 'said "hi"'],
    ]);
  });

  test("parses comma-delimited clipboard data when no tabs exist", () => {
    expect(parseClipboardText('name,company,note\nAda,"Analytical, Engines","line 1\nline 2"')).toEqual([
      ["name", "company", "note"],
      ["Ada", "Analytical, Engines", "line 1\nline 2"],
    ]);
  });

  test("treats plain lines as one column", () => {
    expect(parseClipboardText("Ada\r\nGrace\r\nLinus")).toEqual([["Ada"], ["Grace"], ["Linus"]]);
  });

  test("preserves trailing cells and intentional blank rows but ignores one terminal row break", () => {
    expect(parseClipboardText("a\tb\t\n\n")).toEqual([["a", "b", ""], [""]]);
    expect(parseClipboardText("a,b,")).toEqual([["a", "b", ""]]);
    expect(parseClipboardText("\t")).toEqual([["", ""]]);
    expect(parseClipboardText("")).toEqual([[""]]);
  });
});

describe("grid clipboard value coercion", () => {
  test("matches import shapes for typed columns", () => {
    expect(coerceClipboardValue(" 1,234.50 ", "number")).toBe(1234.5);
    expect(coerceClipboardValue("9,999", "currency")).toBe(9999);
    expect(coerceClipboardValue(" YES ", "boolean")).toBe(true);
    expect(coerceClipboardValue("no", "boolean")).toBe(false);
    expect(coerceClipboardValue("unknown", "boolean")).toBe("unknown");
    expect(coerceClipboardValue('{"ok":true}', "json")).toEqual({ ok: true });
    expect(coerceClipboardValue("sales; enterprise, outbound", "multiselect")).toEqual([
      "sales",
      "enterprise",
      "outbound",
    ]);
  });

  test("maps blanks to null and preserves whitespace in text-like and invalid JSON values", () => {
    expect(coerceClipboardValue("  \n ", "text")).toBeNull();
    expect(coerceClipboardValue("  Ada Lovelace  ", "text")).toBe("  Ada Lovelace  ");
    expect(coerceClipboardValue("  not json  ", "json")).toBe("  not json  ");
    expect(coerceClipboardValue("not a number", "number")).toBe("not a number");
  });
});
