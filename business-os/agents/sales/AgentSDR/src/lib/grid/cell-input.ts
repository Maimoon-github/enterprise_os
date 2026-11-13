import { coerceClipboardValue } from "./clipboard";
import { cleanString } from "./sanitize";
import type { StaticColumnType } from "./types";

export type CellInput = { ok: true; value: unknown } | { ok: false; error: string };

const reject = (error: string): CellInput => ({ ok: false, error });

/**
 * Turns a value sent to the cells endpoint into what the column's type stores.
 *
 * Strings go through the clipboard coercion, so typing, pasting, importing and
 * changing a column's type all agree: a string that converts is stored
 * converted ("1,200" -> 1200), and one that does not ("N/A") is kept as typed
 * rather than refused. Refusing it would make undo, and any paste that
 * includes such a cell, fail on values the app itself stored. Only a non-text
 * value of the wrong shape (an object sent to a number column) is an error.
 */
export function coerceCellInput(value: unknown, type: StaticColumnType): CellInput {
  if (value === null || value === undefined) return { ok: true, value: null };
  const text = typeof value === "string" ? cleanString(value) : null;

  switch (type) {
    case "number":
    case "currency": {
      if (typeof value === "number") return Number.isFinite(value) ? { ok: true, value } : reject("must be a finite number");
      if (text === null) return reject("must be a number");
      const coerced = coerceClipboardValue(text, type);
      return { ok: true, value: coerced };
    }
    case "boolean": {
      if (typeof value === "boolean") return { ok: true, value };
      if (text === null) return reject("must be true or false");
      const coerced = coerceClipboardValue(text, type);
      return { ok: true, value: coerced };
    }
    case "date": {
      if (text === null) return reject("must be a date");
      const trimmed = text.trim();
      if (!trimmed) return { ok: true, value: null };
      return { ok: true, value: trimmed };
    }
    case "json": {
      if (text === null) return { ok: true, value };
      const coerced = coerceClipboardValue(text, type);
      return { ok: true, value: coerced };
    }
    case "multiselect": {
      if (Array.isArray(value)) return value.every((v) => typeof v === "string") ? { ok: true, value } : reject("must be a list of text values");
      return text === null ? reject("must be a list of text values") : { ok: true, value: coerceClipboardValue(text, type) };
    }
    default: {
      // text, url, email, image, select: always a string.
      if (text !== null) return { ok: true, value: text };
      if (typeof value === "number" || typeof value === "boolean") return { ok: true, value: String(value) };
      return reject("must be text");
    }
  }
}
