import type { StaticColumnType } from "./types";

/** Convert a grid value to the string representation used on the clipboard. */
const SPREADSHEET_FORMULA = /^(?:\s*[=+\-@]|[\t\r\n])/;

function clipboardCell(value: unknown, escapeFormulas: boolean): string {
  if (value === null || value === undefined) return "";
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  const text = String(value);
  return escapeFormulas && typeof value === "string" && SPREADSHEET_FORMULA.test(text)
    ? `'${text}`
    : text;
}

function quoteCell(value: string): string {
  // Quote commas as well: a one-cell TSV payload has no tab for the parser to
  // detect, so an unquoted "Acme, Inc" would be mistaken for two CSV cells on
  // a round-trip through this grid.
  return /[,\t\r\n"]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/**
 * Serialize a rectangular selection in the tab-separated format understood by
 * spreadsheet applications. RFC-style quoting keeps tabs, newlines, and
 * quotes inside a cell instead of changing the shape of the selection.
 */
export function serializeClipboardGrid(
  rows: unknown[][],
  options: { escapeFormulas?: boolean } = {},
): string {
  return rows
    .map((row) => row.map((value) => quoteCell(clipboardCell(value, options.escapeFormulas ?? false))).join("\t"))
    .join("\n");
}

/**
 * Parse delimited clipboard text without relying on a browser or XLSX. The
 * parser accepts RFC 4180-style quoted fields, including doubled quotes and
 * embedded line breaks. A terminal line break is treated as a record
 * terminator, not as an additional empty record.
 */
function parseDelimited(text: string, delimiter: "\t" | "," | null): string[][] {
  const normalized = text.replace(/\r\n?/g, "\n");
  if (normalized === "") return [[""]];

  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  let atFieldStart = true;
  let endedOnRowBreak = false;

  const finishField = () => {
    row.push(field);
    field = "";
    atFieldStart = true;
  };
  const finishRow = () => {
    finishField();
    rows.push(row);
    row = [];
  };

  for (let i = 0; i < normalized.length; i += 1) {
    const char = normalized[i];

    if (quoted) {
      if (char === '"') {
        if (normalized[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          quoted = false;
        }
      } else {
        field += char;
      }
      endedOnRowBreak = false;
      continue;
    }

    if (char === '"' && atFieldStart) {
      quoted = true;
      atFieldStart = false;
      endedOnRowBreak = false;
    } else if (delimiter !== null && char === delimiter) {
      finishField();
      endedOnRowBreak = false;
    } else if (char === "\n") {
      finishRow();
      endedOnRowBreak = true;
    } else {
      field += char;
      atFieldStart = false;
      endedOnRowBreak = false;
    }
  }

  if (!endedOnRowBreak || row.length > 0 || field !== "") finishRow();
  return rows;
}

/**
 * Parse copied spreadsheet data. Spreadsheet clipboard payloads are normally
 * TSV; CSV is accepted for cross-platform paste, and plain lines become a
 * single column.
 */
export function parseClipboardText(text: string): string[][] {
  const delimiter = text.includes("\t") ? "\t" : text.includes(",") ? "," : null;
  return parseDelimited(text, delimiter);
}

const CURRENCY_SYMBOLS = /[$€£¥₹]/g;
const CURRENCY_CODES = /^(?:USD|EUR|GBP|JPY|INR|CAD|AUD|CHF|CNY|SGD|AED)\s*|\s*(?:USD|EUR|GBP|JPY|INR|CAD|AUD|CHF|CNY|SGD|AED)$/i;
const DECIMAL_TEXT = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i;

/**
 * Reads a number a person would type: "1,234.5", "$1,234.50", "€ 99", "USD 12",
 * "-$5", "(1,200)" (accounting negative). Returns null when the text is not
 * entirely a number, so "N/A", "12abc" and "50%" are left to the caller.
 */
export function parseNumericText(text: string): number | null {
  let value = text.trim();
  if (!value) return null;
  let negative = false;
  const wrapped = /^\((.*)\)$/.exec(value);
  if (wrapped) {
    negative = true;
    value = wrapped[1].trim();
  }
  value = value.replace(CURRENCY_CODES, "").replace(CURRENCY_SYMBOLS, "").replace(/,/g, "").replace(/\s+/g, "");
  if (!DECIMAL_TEXT.test(value)) return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return negative ? -number : number;
}

/**
 * Coerce a pasted string to the persisted value shape of a static grid column.
 * Text-like values retain their exact whitespace; only blank detection and
 * typed parsing use a trimmed representation.
 */
export function coerceClipboardValue(raw: string, type: StaticColumnType): unknown {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  switch (type) {
    case "number":
    case "currency": {
      const value = parseNumericText(trimmed);
      // Preserve malformed input instead of silently clearing an existing
      // cell. Inline editing already permits the same raw string shape.
      return value ?? raw;
    }
    case "boolean": {
      const normalized = trimmed.toLowerCase();
      if (["true", "yes", "y", "1"].includes(normalized)) return true;
      if (["false", "no", "n", "0"].includes(normalized)) return false;
      return raw;
    }
    case "json":
      try {
        return JSON.parse(raw);
      } catch {
        return raw;
      }
    case "multiselect":
      return raw.split(/[;,]/).map((value) => value.trim()).filter(Boolean);
    default:
      return raw;
  }
}
