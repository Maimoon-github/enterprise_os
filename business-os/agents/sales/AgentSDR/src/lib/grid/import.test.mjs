import { describe, expect, test } from "bun:test";
import * as XLSX from "xlsx";

import { isInitialPlaceholderRow, isInitialSeedColumn, parseSpreadsheet } from "./import.ts";

describe("grid spreadsheet imports", () => {
  test("does not import a formatted-but-empty first data row from Excel", () => {
    const workbook = XLSX.utils.book_new();
    const sheet = XLSX.utils.aoa_to_sheet([
      ["Email", "Company"],
      ["", ""],
      ["ada@example.com", "Analytical Engines"],
    ]);
    XLSX.utils.book_append_sheet(workbook, sheet, "Leads");
    const buffer = XLSX.write(workbook, { type: "array", bookType: "xlsx" });

    const parsed = parseSpreadsheet(buffer);

    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(parsed.sheet.totalRows).toBe(1);
    expect(parsed.sheet.rows).toEqual([["ada@example.com", "Analytical Engines"]]);
  });

  test("identifies only a sole empty seed row as replaceable", () => {
    expect(isInitialPlaceholderRow([{ cells: {}, cellMeta: {} }])).toBe(true);
    expect(isInitialPlaceholderRow([{ cells: { email: "ada@example.com" }, cellMeta: {} }])).toBe(false);
    expect(isInitialPlaceholderRow([{ cells: {}, cellMeta: {} }, { cells: {}, cellMeta: {} }])).toBe(false);
  });

  test("identifies only the untouched starter column as reusable", () => {
    expect(isInitialSeedColumn([{ key: "name", name: "New Column" }])).toBe(true);
    expect(isInitialSeedColumn([{ key: "email", name: "Email" }])).toBe(false);
    expect(isInitialSeedColumn([{ key: "name", name: "New Column" }, { key: "email", name: "Email" }])).toBe(false);
  });
});
