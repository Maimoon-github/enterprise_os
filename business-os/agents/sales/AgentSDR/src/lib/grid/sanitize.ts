/**
 * Makes a value safe to write into a jsonb column.
 *
 * Postgres rejects \u0000 in text and jsonb outright, and JSON.stringify
 * emits a lone surrogate as an escape (\ud800) that jsonb rejects too. A
 * provider or model can return either, and one such string would make the
 * completion write throw — after the paid call had already succeeded — so
 * the job would be retried and billed again.
 */
export function cleanString(text: string): string {
  const withoutNul = text.replace(/\u0000/g, "");
  return withoutNul.replace(
    /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/g,
    "�",
  );
}

/** Deep-cleans strings and object keys; everything else passes through. */
export function cleanJson<T>(value: T, depth = 0): T {
  if (typeof value === "string") return cleanString(value) as T;
  if (!value || typeof value !== "object") return value;
  if (depth > 40) return null as T;
  const withToJson = value as { toJSON?: () => unknown };
  if (typeof withToJson.toJSON === "function") return cleanJson(withToJson.toJSON(), depth + 1) as T;
  if (Array.isArray(value)) return value.map((item) => cleanJson(item, depth + 1)) as T;
  const out: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) out[cleanString(key)] = cleanJson(item, depth + 1);
  return out as T;
}
