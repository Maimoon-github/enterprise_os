/**
 * Request-boundary checks shared by the grid routes.
 *
 * A malformed id or name used to travel into a query and come back as a 500
 * (or a 400 carrying raw SQL text). These helpers reject it at the edge:
 * a bad id in a URL is a 404 (the thing cannot exist), a bad value in a body
 * or query string is a 400. Pure, so they are unit-tested without a database.
 */

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Longest name accepted for a table, workbook, folder or column. */
export const MAX_NAME_LENGTH = 200;

export function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_RE.test(value);
}

export type Parsed<T> = { ok: true; value: T } | { ok: false; error: string };

/**
 * A required, non-blank string. Returned trimmed; rejects non-strings,
 * whitespace-only text and anything past MAX_NAME_LENGTH.
 */
export function requireString(
  value: unknown,
  label: string,
  maxLength = MAX_NAME_LENGTH,
): Parsed<string> {
  if (typeof value !== "string") return { ok: false, error: `${label} must be text` };
  const trimmed = value.trim();
  if (!trimmed) return { ok: false, error: `${label} cannot be empty` };
  if (trimmed.length > maxLength) {
    return { ok: false, error: `${label} must be ${maxLength} characters or fewer` };
  }
  return { ok: true, value: trimmed };
}

/**
 * An optional name: undefined passes through, anything else must be valid.
 * `blankMeansDefault` is for create endpoints, where "" falls back to the
 * default name; renames leave it off so "" is a 400 rather than an empty name.
 */
export function optionalName(
  value: unknown,
  label = "name",
  blankMeansDefault = false,
): Parsed<string | undefined> {
  if (value === undefined) return { ok: true, value: undefined };
  if (blankMeansDefault && typeof value === "string" && !value.trim()) return { ok: true, value: undefined };
  return requireString(value, label);
}

/** A UUID, or null/absent where a nullable reference (folder) is allowed. */
export function nullableUuid(value: unknown, label: string): Parsed<string | null | undefined> {
  if (value === undefined) return { ok: true, value: undefined };
  if (value === null) return { ok: true, value: null };
  return isUuid(value) ? { ok: true, value } : { ok: false, error: `${label} is not a valid id` };
}

/**
 * Integer query parameter. Absent -> `fallback`; present but not a whole
 * number within [min, max] -> null (the caller answers 400).
 */
export function intParam(
  raw: string | null,
  fallback: number,
  { min = 0, max = Number.MAX_SAFE_INTEGER }: { min?: number; max?: number } = {},
): number | null {
  if (raw === null) return fallback;
  if (!/^\d+$/.test(raw.trim())) return null;
  const n = Number(raw);
  return Number.isSafeInteger(n) && n >= min && n <= max ? n : null;
}

/** A parsed JSON body that is a plain object (not null, an array or a scalar). */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * The message to show a caller for a thrown error. Our own validation errors
 * pass through; database failures (postgres-js errors carry a `code`, drizzle
 * wraps them as "Failed query: <sql> params: …") are replaced by `fallback`
 * so no SQL text or bound values reach a response body.
 */
export function clientMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) return fallback;
  const code = (error as { code?: unknown }).code;
  if (typeof code === "string" || "query" in error || /^Failed query/i.test(error.message)) return fallback;
  return error.message || fallback;
}
