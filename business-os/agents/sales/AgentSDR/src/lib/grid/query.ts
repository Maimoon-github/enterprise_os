import { sql, type SQL } from "drizzle-orm";
import { gridRows } from "./schema";
import type { ColumnType, TableView } from "./types";

/**
 * Filtering and sorting over the JSONB value plane.
 *
 * Nothing here is string-interpolated into SQL: column keys and user values
 * alike are bound as parameters by drizzle's sql template, so `cells ->> $1`
 * is injection-safe on its own. assertKnownColumns() is defence in depth: it
 * drops saved-view entries naming a column that has since been deleted (or
 * otherwise invalid), so an old view can never make a table unopenable.
 * validateView() is the strict check run when a view is saved.
 */

/** Matches Clay's operator dropdown, in its order. */
export const FILTER_OPERATORS = [
  "eq",
  "neq",
  "gt",
  "gte",
  "lt",
  "lte",
  "empty",
  "notEmpty",
  "contains",
  "notContains",
] as const;

export type FilterOperator = (typeof FILTER_OPERATORS)[number];

export const OPERATOR_LABELS: Record<FilterOperator, string> = {
  eq: "equal to",
  neq: "not equal to",
  gt: "greater than",
  gte: "greater or equal to",
  lt: "less than",
  lte: "less or equal to",
  empty: "is empty",
  notEmpty: "is not empty",
  contains: "contains",
  notContains: "does not contain",
};

/** Operators that ignore the value box — the UI hides it for these. */
export const VALUELESS_OPERATORS: ReadonlySet<FilterOperator> = new Set(["empty", "notEmpty"]);

export type FilterCondition = {
  columnKey: string;
  operator: FilterOperator;
  value?: string;
  /** Muted by the eye toggle — kept in the view but not applied. */
  disabled?: boolean;
};

export type FilterGroup = {
  conjunction: "and" | "or";
  conditions: (FilterCondition | FilterGroup)[];
};

export type SortSpec = { columnKey: string; direction: "asc" | "desc" };

export type GridQuery = {
  filters?: FilterGroup;
  sorts?: SortSpec[];
  /** Free-text search across every visible column. */
  search?: string;
};

export function isFilterGroup(c: FilterCondition | FilterGroup): c is FilterGroup {
  return (c as FilterGroup).conditions !== undefined;
}

/* -------------------------------------------------------------------------- */

/**
 * Numbers are the only type needing a cast, and the cast has to be guarded:
 * a single non-numeric string in the column would otherwise abort the whole
 * query with "invalid input syntax for type numeric".
 *
 * Dates deliberately compare as text. Values are stored ISO-8601, which sorts
 * and compares lexicographically in the right order, so a cast buys nothing
 * and would carry the same failure mode.
 */
function valueExpr(columnKey: string, type: ColumnType): SQL {
  const raw = sql`${gridRows.cells} ->> ${columnKey}`;
  if (type === "number" || type === "currency") {
    return sql`(CASE WHEN ${raw} ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN (${raw})::numeric END)`;
  }
  return raw;
}

/** Bind the comparison value in the same shape as the column expression. */
function boundValue(value: string, type: ColumnType): SQL {
  if (type === "number" || type === "currency") {
    const n = Number(String(value).replace(/,/g, ""));
    return sql`${Number.isFinite(n) ? n : null}::numeric`;
  }
  return sql`${value}`;
}

/**
 * Escapes LIKE metacharacters so "50%" or "a_b" match literally. Used with
 * `ESCAPE '\\'` — without it a bare "%" or "_" matches every row.
 */
export function escapeLike(value: string): string {
  return value.replace(/[\\%_]/g, (ch) => `\\${ch}`);
}

function likePattern(value: string): string {
  return `%${escapeLike(value)}%`;
}

function conditionSql(
  c: FilterCondition,
  types: Map<string, ColumnType>,
): SQL | null {
  const type = types.get(c.columnKey);
  if (!type) return null; // column deleted since the view was saved — ignore it

  const left = valueExpr(c.columnKey, type);
  const raw = sql`${gridRows.cells} ->> ${c.columnKey}`;

  switch (c.operator) {
    case "empty":
      return sql`(${raw} IS NULL OR ${raw} = '')`;
    case "notEmpty":
      return sql`(${raw} IS NOT NULL AND ${raw} <> '')`;
    default:
      break;
  }

  // Every other operator needs a value; a blank one is treated as "no filter"
  // rather than as an empty-string comparison, which is almost never intended
  // and would silently hide every row while the user is still typing.
  const value = c.value ?? "";
  if (value === "") return null;

  switch (c.operator) {
    case "eq":
      return sql`${left} = ${boundValue(value, type)}`;
    case "neq":
      // NULL <> x is NULL, not true, so an unset cell would drop out of a
      // "not equal to" result. Treat unset as not-equal, which is what the
      // filter plainly means.
      return sql`(${left} IS DISTINCT FROM ${boundValue(value, type)})`;
    case "gt":
      return sql`${left} > ${boundValue(value, type)}`;
    case "gte":
      return sql`${left} >= ${boundValue(value, type)}`;
    case "lt":
      return sql`${left} < ${boundValue(value, type)}`;
    case "lte":
      return sql`${left} <= ${boundValue(value, type)}`;
    case "contains":
      return sql`${raw} ILIKE ${likePattern(value)} ESCAPE '\\'`;
    case "notContains":
      return sql`(${raw} IS NULL OR ${raw} NOT ILIKE ${likePattern(value)} ESCAPE '\\')`;
    default:
      return null;
  }
}

function groupSql(group: FilterGroup, types: Map<string, ColumnType>): SQL | null {
  const parts = group.conditions
    .filter((c) => isFilterGroup(c) || !c.disabled)
    .map((c) => (isFilterGroup(c) ? groupSql(c, types) : conditionSql(c, types)))
    .filter((p): p is SQL => p !== null);

  if (!parts.length) return null;
  if (parts.length === 1) return parts[0];

  const joiner = group.conjunction === "or" ? sql` OR ` : sql` AND `;
  return sql`(${sql.join(parts, joiner)})`;
}

/** Case-insensitive match on any of the given columns. */
function searchSql(term: string, columnKeys: string[]): SQL | null {
  const t = term.trim();
  if (!t || !columnKeys.length) return null;

  const parts = columnKeys.map(
    (k) => sql`${gridRows.cells} ->> ${k} ILIKE ${likePattern(t)} ESCAPE '\\'`,
  );
  return sql`(${sql.join(parts, sql` OR `)})`;
}

/**
 * The WHERE fragment for a query, or null when nothing narrows the result.
 * Callers AND this with the table-id predicate.
 */
export function buildWhere(
  query: GridQuery,
  columns: { key: string; type: ColumnType }[],
): SQL | null {
  const types = new Map(columns.map((c) => [c.key, c.type]));
  const parts: SQL[] = [];

  if (query.filters) {
    const f = groupSql(query.filters, types);
    if (f) parts.push(f);
  }

  if (query.search) {
    const s = searchSql(
      query.search,
      columns.map((c) => c.key),
    );
    if (s) parts.push(s);
  }

  if (!parts.length) return null;
  return parts.length === 1 ? parts[0] : sql`(${sql.join(parts, sql` AND `)})`;
}

/**
 * ORDER BY for a query. Always ends with `position` so the result is stable:
 * without a tiebreaker, rows with equal sort values can come back in a
 * different order on every request and appear to shuffle as the user scrolls.
 */
export function buildOrderBy(
  sorts: SortSpec[] | undefined,
  columns: { key: string; type: ColumnType }[],
): SQL {
  const types = new Map(columns.map((c) => [c.key, c.type]));
  const parts: SQL[] = [];

  for (const s of sorts ?? []) {
    const type = types.get(s.columnKey);
    if (!type) continue;
    const expr = valueExpr(s.columnKey, type);
    // NULLS LAST in both directions: an unset cell is "no value", and pushing
    // those to the top of a descending sort buries the rows that matter.
    parts.push(
      s.direction === "desc" ? sql`${expr} DESC NULLS LAST` : sql`${expr} ASC NULLS LAST`,
    );
  }

  parts.push(sql`${gridRows.position} ASC`);
  return sql.join(parts, sql`, `);
}

/* -------------------------------------------------------------------------- */

/**
 * Drops filters and sorts a table can no longer apply, in place.
 *
 * A saved view outlives the columns it names: a column deleted after the view
 * was saved, or a view written before PATCH validated it, must degrade to "that
 * filter is ignored" rather than a 400 on every later read of the table. Also
 * the check that lets valueExpr() trust a key — whatever survives is a column
 * the table has, with a known operator or direction.
 */
export function assertKnownColumns(query: GridQuery, known: Set<string>): void {
  if (query.filters) query.filters = pruneFilterGroup(query.filters, known);
  if (query.sorts) query.sorts = pruneSorts(query.sorts, known);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function pruneFilterGroup(group: unknown, known: Set<string>): FilterGroup {
  const raw = isObject(group) && Array.isArray(group.conditions) ? group : { conditions: [] };
  const conditions: (FilterCondition | FilterGroup)[] = [];
  for (const c of raw.conditions as unknown[]) {
    if (!isObject(c)) continue;
    if (Array.isArray(c.conditions)) {
      conditions.push(pruneFilterGroup(c, known));
      continue;
    }
    if (typeof c.columnKey !== "string" || !known.has(c.columnKey)) continue;
    if (!FILTER_OPERATORS.includes(c.operator as FilterOperator)) continue;
    const value =
      typeof c.value === "string" ? c.value
      : typeof c.value === "number" || typeof c.value === "boolean" ? String(c.value)
      : undefined;
    conditions.push({
      columnKey: c.columnKey,
      operator: c.operator as FilterOperator,
      ...(value !== undefined ? { value } : {}),
      ...(c.disabled === true ? { disabled: true } : {}),
    });
  }
  return { conjunction: raw.conjunction === "or" ? "or" : "and", conditions };
}

function pruneSorts(sorts: unknown, known: Set<string>): SortSpec[] {
  if (!Array.isArray(sorts)) return [];
  return sorts.filter(
    (s): s is SortSpec =>
      isObject(s) &&
      typeof s.columnKey === "string" &&
      known.has(s.columnKey) &&
      (s.direction === "asc" || s.direction === "desc"),
  ).map((s) => ({ columnKey: s.columnKey, direction: s.direction }));
}

/**
 * A copy of a saved view with everything the table cannot apply removed.
 * Hidden/pinned lists are reduced to known column keys as well.
 */
export function sanitizeView(view: unknown, known: Set<string>): TableView {
  if (!isObject(view)) return {};
  const keys = (value: unknown) =>
    Array.isArray(value) ? value.filter((k): k is string => typeof k === "string" && known.has(k)) : undefined;
  const out: TableView = {};
  const hidden = keys(view.hiddenColumns);
  const pinned = keys(view.pinnedColumns);
  if (hidden) out.hiddenColumns = hidden;
  if (pinned) out.pinnedColumns = pinned;
  if (isObject(view.filters)) out.filters = pruneFilterGroup(view.filters, known);
  if (Array.isArray(view.sorts)) out.sorts = pruneSorts(view.sorts, known);
  return out;
}

const MAX_VIEW_DEPTH = 6;
const MAX_VIEW_CONDITIONS = 200;

/**
 * Strict check for a view being SAVED: returns a message for the first
 * problem, or null. Reads stay tolerant (see assertKnownColumns); this keeps
 * new junk from being stored in the first place.
 */
export function validateView(view: unknown, known: Set<string>): string | null {
  if (!isObject(view)) return "view must be an object";

  for (const field of ["hiddenColumns", "pinnedColumns"] as const) {
    const list = view[field];
    if (list === undefined) continue;
    if (!Array.isArray(list) || list.some((k) => typeof k !== "string")) {
      return `${field} must be an array of column keys`;
    }
  }

  if (view.sorts !== undefined) {
    if (!Array.isArray(view.sorts)) return "sorts must be an array";
    for (const s of view.sorts) {
      if (!isObject(s) || typeof s.columnKey !== "string") return "Each sort needs a columnKey";
      if (!known.has(s.columnKey)) return `Unknown column in sort: "${s.columnKey}"`;
      if (s.direction !== "asc" && s.direction !== "desc") return "Sort direction must be asc or desc";
    }
  }

  if (view.filters !== undefined) {
    let seen = 0;
    const visit = (group: unknown, depth: number): string | null => {
      if (!isObject(group) || !Array.isArray(group.conditions)) return "filters must be a group with a conditions array";
      if (group.conjunction !== "and" && group.conjunction !== "or") return "Filter conjunction must be and or or";
      if (depth > MAX_VIEW_DEPTH) return "Filters are nested too deeply";
      for (const c of group.conditions) {
        if (++seen > MAX_VIEW_CONDITIONS) return "Too many filter conditions";
        if (!isObject(c)) return "Each filter must be an object";
        if (Array.isArray(c.conditions)) {
          const nested = visit(c, depth + 1);
          if (nested) return nested;
          continue;
        }
        if (typeof c.columnKey !== "string") return "Each filter needs a columnKey";
        if (!known.has(c.columnKey)) return `Unknown column in filter: "${c.columnKey}"`;
        if (!FILTER_OPERATORS.includes(c.operator as FilterOperator)) return `Unknown filter operator: "${String(c.operator)}"`;
        const v = c.value;
        if (v !== undefined && v !== null && typeof v !== "string" && typeof v !== "number" && typeof v !== "boolean") {
          return "A filter value must be text";
        }
      }
      return null;
    };
    const problem = visit(view.filters, 0);
    if (problem) return problem;
  }
  return null;
}
