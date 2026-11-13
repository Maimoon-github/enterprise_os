/** UTF-8 byte-order mark. Excel uses it to reliably detect UTF-8 CSV files. */
export const UTF8_BOM = "\uFEFF";

/**
 * Text beginning with one of these characters can be interpreted as a formula
 * by spreadsheet applications. Prefixing an apostrophe keeps exported user
 * data inert while preserving the visible value in Excel and Google Sheets.
 */
const SPREADSHEET_FORMULA = /^(?:\s*[=+\-@]|[\t\r\n])/;

function printableValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") {
    return SPREADSHEET_FORMULA.test(value) ? `'${value}` : value;
  }
  if (typeof value === "number" || typeof value === "bigint" || typeof value === "boolean") {
    return String(value);
  }
  if (typeof value === "object") {
    return JSON.stringify(value) ?? "";
  }
  return String(value);
}

/** Serializes one value according to RFC 4180-style CSV quoting rules. */
export function csvCell(value: unknown): string {
  const text = printableValue(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** Serializes rows as comma-separated UTF-8 text with CRLF record separators. */
export function serializeCsv(rows: readonly (readonly unknown[])[]): string {
  return rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
}
