/**
 * Shared types for the lead database — see src/lib/leads/columns.ts for the
 * custom-field registry (values live in people.custom / companies.custom).
 *
 * Kept separate from schema.ts because both the server (import, queries) and
 * the client (column settings, mapping dialog) need these, and schema.ts pulls
 * in drizzle-orm, which has no business in a client bundle. Same split, and
 * for the same reason, as src/lib/grid/types.ts.
 */
import type { StaticColumnType } from "@/lib/grid/types";

/**
 * Lead columns are always static. Runner types (enrichment, ai, waterfall)
 * belong to the grid: enrichment happens there, and the result is pushed here
 * as a plain value. A people/companies column never executes anything.
 */
export type LeadColumnType = StaticColumnType;

export type LeadEntity = "person" | "company";

export const LEAD_ENTITIES: readonly LeadEntity[] = ["person", "company"];

export function isLeadEntity(value: string): value is LeadEntity {
  return (LEAD_ENTITIES as readonly string[]).includes(value);
}

/**
 * The storage kind of a custom field's value inside the `custom` jsonb.
 *
 * There is no physical column any more (custom fields are keys in
 * people.custom / companies.custom), so this names how the JSON value is
 * stored and which cast filters and sorts apply to it: text -> JSON string,
 * numeric -> JSON number, boolean -> JSON boolean, timestamptz -> ISO-8601
 * JSON string, text[] -> JSON array of strings, jsonb -> any JSON. The
 * name is kept for the registry column `entity_columns.pg_type`.
 */
export type LeadPgType = "text" | "numeric" | "boolean" | "timestamptz" | "jsonb" | "text[]";

/**
 * UI type -> physical type.
 *
 * Several UI types collapse to `text` on purpose: `email`, `url` and `select`
 * differ in how they render, validate and filter, not in how they store. That
 * distinction lives in entity_columns.type, so it survives without costing a
 * domain type or a check constraint that would make the column expensive to
 * alter later.
 */
export const PG_TYPE_FOR_COLUMN_TYPE: Record<LeadColumnType, LeadPgType> = {
  text: "text",
  url: "text",
  email: "text",
  image: "text",
  select: "text",
  number: "numeric",
  currency: "numeric",
  boolean: "boolean",
  date: "timestamptz",
  multiselect: "text[]",
  json: "jsonb",
};

/** A registry row, in the shape both server and client use. */
export type LeadColumn = {
  id: string;
  entity: LeadEntity;
  /** The key inside people.custom / companies.custom (core rows: the real column). Immutable. */
  key: string;
  /** The display label. Renameable; a rename only touches the registry row. */
  name: string;
  type: LeadColumnType;
  pgType: LeadPgType;
  config: Record<string, unknown>;
  isCore: boolean;
  position: number;
  archivedAt: Date | null;
};

// ---------------------------------------------------------------------------
// Core columns
// ---------------------------------------------------------------------------

/**
 * Core columns ship with the table: they cannot be dropped or retyped, because
 * the importer, the identity rules and the queries all reference them by name.
 *
 * Every organization gets its own copy of these registry rows, created lazily
 * the first time its registry is read (ensureCoreColumns in ./columns.ts) —
 * nothing depends on a sign-up hook. scripts/create-lead-tables.ts seeded the
 * original organization's copy.
 *
 * `people.company_id` is absent on purpose — it is a relation, not a mappable
 * field. The importer derives it from the company's domain.
 */
export const CORE_COLUMN_DEFS: readonly {
  entity: LeadEntity;
  key: string;
  name: string;
  type: LeadColumnType;
}[] = [
  { entity: "company", key: "domain", name: "Domain", type: "url" },
  { entity: "company", key: "name", name: "Company Name", type: "text" },
  { entity: "company", key: "linkedin_url", name: "Company LinkedIn", type: "url" },

  { entity: "person", key: "email", name: "Email", type: "email" },
  { entity: "person", key: "linkedin_url", name: "LinkedIn URL", type: "url" },
  { entity: "person", key: "first_name", name: "First Name", type: "text" },
  { entity: "person", key: "last_name", name: "Last Name", type: "text" },
  { entity: "person", key: "full_name", name: "Full Name", type: "text" },
  { entity: "person", key: "title", name: "Job Title", type: "text" },
  { entity: "person", key: "profile_picture_url", name: "Profile Picture", type: "image" },
  { entity: "person", key: "phone", name: "Phone", type: "text" },
];

export const CORE_COLUMN_KEYS: Record<LeadEntity, readonly string[]> = {
  company: CORE_COLUMN_DEFS.filter((c) => c.entity === "company").map((c) => c.key),
  person: CORE_COLUMN_DEFS.filter((c) => c.entity === "person").map((c) => c.key),
};

/**
 * Columns that physically exist on the table but are never user-editable and
 * never appear in the mapping catalog. A generated field key must not
 * collide with one of these — which the `x_` prefix below guarantees, but the
 * list is kept explicit so the guarantee is checkable.
 */
export const RESERVED_COLUMN_NAMES: readonly string[] = [
  "id",
  "organization_id",
  "custom",
  "raw",
  "source",
  "company_id",
  "created_at",
  "updated_at",
];

// ---------------------------------------------------------------------------
// Custom field keys
// ---------------------------------------------------------------------------

/**
 * Every user-added field key is prefixed, which is what makes name generation
 * total rather than best-effort.
 *
 * With the prefix, a generated name can never collide with a core column, a
 * core column we add in a future release, a reserved SQL word, or one of the
 * bookkeeping columns above. Without it, every one of those is a case to
 * handle, and the fourth one gets missed.
 */
const USER_COLUMN_PREFIX = "x_";

/** Postgres truncates identifiers at 63 bytes; leave room for a dedupe suffix. */
const MAX_IDENTIFIER_BYTES = 63;
const MAX_BASE_BYTES = MAX_IDENTIFIER_BYTES - 4;

/**
 * "Company Size (2024)" -> "x_company_size_2024".
 *
 * snake_case rather than the camelCase of toColumnKey() in grid/columns.ts,
 * because this becomes a real Postgres identifier. Unquoted identifiers fold
 * to lowercase, so a camelCase name would only work if every reference quoted
 * it — one missed quote away from a confusing "column does not exist".
 */
export function toPhysicalColumnName(label: string): string {
  const slug = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

  // Truncate BEFORE the uniqueness suffix is appended, not after: suffixing a
  // name that is already at the limit would push it over, and Postgres would
  // silently truncate it back into a collision with the name it was avoiding.
  const truncated = slug.slice(0, MAX_BASE_BYTES - USER_COLUMN_PREFIX.length);

  return `${USER_COLUMN_PREFIX}${truncated || "column"}`;
}

/** Appends a numeric suffix until the physical name is free on this entity. */
export function uniquePhysicalColumnName(label: string, taken: Set<string>): string {
  const base = toPhysicalColumnName(label);
  if (!taken.has(base)) return base;
  let n = 2;
  while (taken.has(`${base}_${n}`)) n += 1;
  return `${base}_${n}`;
}

/** True if this field was added by a user (a key in `custom`) rather than a core column. */
export function isUserColumn(key: string): boolean {
  return key.startsWith(USER_COLUMN_PREFIX);
}
