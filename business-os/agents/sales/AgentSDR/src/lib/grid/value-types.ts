import { getIntegrationAction } from "@/lib/integrations/catalog";
import type { AiOutputConfig, ColumnConfig, ColumnType, IntegrationOutputConfig, StaticColumnType } from "./types";

type ColumnLike = { type: ColumnType; config?: ColumnConfig; name?: string };

/** The storage type may be integration_output while its displayed value is a URL, date, etc. */
export function effectiveColumnType(column: ColumnLike): ColumnType {
  if (column.type === "ai_output") return (column.config as AiOutputConfig).valueType ?? "text";
  if (column.type !== "integration_output") return column.type;
  const config = (column.config ?? {}) as IntegrationOutputConfig;
  if (config.valueType) return config.valueType;
  const catalogType = getIntegrationAction(config.integrationKey, config.actionKey)
    ?.outputs.find((output) => output.key === config.outputKey)
    ?.columnType;
  if (catalogType) return catalogType;
  return inferResponseValueType(undefined, `${column.name ?? ""} ${config.outputKey ?? ""}`);
}

/** Infer API response values conservatively; field-name hints break ambiguous string ties. */
export function inferResponseValueType(value: unknown, fieldName = ""): StaticColumnType {
  const name = fieldName.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "number") return "number";
  if (value !== null && typeof value === "object") return "json";

  const text = typeof value === "string" ? value.trim() : "";
  const emailLike = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text);
  if (emailLike || (!text && /(^| )(email|email address)($| )/.test(name))) return "email";

  const urlLike = /^(https?:\/\/|www\.)\S+$/i.test(text)
    || /^[a-z0-9.-]+\.[a-z]{2,}(?:\/\S*)?$/i.test(text);
  const imageHint = /(^| )(image|avatar|photo|picture|logo|thumbnail)($| )/.test(name);
  if ((urlLike || !text) && imageHint) return "image";
  if (urlLike || (!text && /(^| )(url|uri|website|domain|link|profile)($| )/.test(name))) return "url";

  const isoDate = /^\d{4}-\d{2}-\d{2}(?:[T ][0-2]\d:[0-5]\d(?::[0-5]\d(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/.test(text);
  const dateHint = /(^| )(date|time|timestamp|created at|updated at|last updated)($| )/.test(name);
  if (!text && dateHint) return "date";
  if ((isoDate || dateHint) && text && !Number.isNaN(Date.parse(text))) return "date";

  const numericHint = /(^| )(count|total|number|score|amount|price|credits|employees|page|year|founded)($| )/.test(name);
  if (!text && numericHint) return "number";
  if (numericHint && /^-?\d+(?:\.\d+)?$/.test(text)) return "number";
  const booleanHint = /(^| )(is|has|can|verified|valid|active|enabled|webmail|disposable|gibberish)($| )/.test(name);
  if (!text && booleanHint) return "boolean";
  if (text === "true" || text === "false") return "boolean";
  return "text";
}

export function displayHref(value: unknown, type: ColumnType): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  if (type === "email") return `mailto:${value.trim()}`;
  if (type !== "url" && type !== "image") return null;
  const text = value.trim();
  return /^https?:\/\//i.test(text) ? text : `https://${text.replace(/^www\./i, "")}`;
}

/** Column types whose cells hold plain strings, so they can feed a string-valued enrichment input. */
const TEXT_LIKE_COLUMN_TYPES: ReadonlySet<ColumnType> = new Set(["text", "url", "email", "select"]);

/**
 * Whether a column of effective type `columnType` (see effectiveColumnType, which
 * already resolves ai_output / integration_output to their value type) may be
 * mapped to an enrichment input that declares `accepted` column types.
 *
 *  - an exact match always works;
 *  - an input that accepts any of text / url / email is string-valued, so every
 *    text-like column (text, url, email, select) works for it — a CSV import
 *    leaves domains and names as plain text, and the run validates each value;
 *  - a formula column's output type is unknown until it runs, so it is accepted
 *    anywhere and each value is checked at run time.
 * Clearly incompatible types (boolean, json, number for a domain...) stay rejected.
 */
export function inputAcceptsColumnType(accepted: readonly StaticColumnType[], columnType: ColumnType): boolean {
  if (accepted.some((type) => type === columnType)) return true;
  if (columnType === "formula") return true;
  const stringInput = accepted.some((type) => type === "text" || type === "url" || type === "email");
  return stringInput && TEXT_LIKE_COLUMN_TYPES.has(columnType);
}

/** "text, URL or email" — for messages about what an input can be mapped to. */
export function describeAcceptedInputTypes(accepted: readonly StaticColumnType[]): string {
  const stringInput = accepted.some((type) => type === "text" || type === "url" || type === "email");
  const names = stringInput ? ["text", "URL", "email", "select", "formula"] : [...accepted, "formula"];
  return names.length > 1 ? `${names.slice(0, -1).join(", ")} or ${names.at(-1)}` : names[0];
}
