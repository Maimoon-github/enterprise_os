import "server-only";
import { and, asc, eq, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { inOrgTables } from "./scope";
import { gridColumns, gridRows, gridTables } from "./schema";
import type { FormulaConfig, FormulaLookupRef, FormulaLookupRegistry } from "./types";
import { tokensIn } from "./runners/types";
import { effectiveColumnType } from "./value-types";

const MAX_LOOKUP_ROWS = 50_000;

type ParsedLookup = Pick<FormulaLookupRef, "tableToken" | "lookupColumnToken" | "returnColumnToken">;

export async function resolveFormulaConfig(
  tableId: string,
  expression: string,
  previousRefs: FormulaLookupRef[] = [],
): Promise<FormulaConfig> {
  const [current] = await db.select().from(gridTables).where(and(inOrg(gridTables), eq(gridTables.id, tableId))).limit(1);
  if (!current) throw new Error("Table not found");
  const tables = await db.select().from(gridTables).where(and(inOrg(gridTables), eq(gridTables.workbookId, current.workbookId)));
  const tableIds = tables.map((table) => table.id);
  const columns = tableIds.length
    ? await db.select().from(gridColumns).where(and(inOrgTables(gridColumns.tableId), inArray(gridColumns.tableId, tableIds)))
    : [];

  const currentKeys = new Set(columns.filter((column) => column.tableId === tableId).map((column) => column.key));
  const unknownToken = tokensIn(expression).find((key) => !currentKeys.has(key));
  if (unknownToken) throw new Error(`Formula references unknown column “${unknownToken}”`);

  const refs = parseLookupCalls(expression).map((call) => {
    const previous = previousRefs.find((ref) =>
      ref.tableToken.toLowerCase() === call.tableToken.toLowerCase()
      && ref.lookupColumnToken.toLowerCase() === call.lookupColumnToken.toLowerCase()
      && ref.returnColumnToken.toLowerCase() === call.returnColumnToken.toLowerCase(),
    );
    const matchingTables = tables.filter((table) =>
      table.id === call.tableToken
      || table.name.toLowerCase() === call.tableToken.toLowerCase()
      || (previous?.tableId === table.id),
    );
    if (matchingTables.length !== 1) throw new Error(`LOOKUP table “${call.tableToken}” is unknown or ambiguous`);
    const table = matchingTables[0];
    const tableColumns = columns.filter((column) => column.tableId === table.id);
    const resolveColumn = (token: string, previousKey?: string) => {
      const matches = tableColumns.filter((column) =>
        column.id === token
        || column.key === token
        || column.name.toLowerCase() === token.toLowerCase()
        || column.key === previousKey,
      );
      if (matches.length !== 1) throw new Error(`LOOKUP column “${token}” in “${table.name}” is unknown or ambiguous`);
      return matches[0];
    };
    return {
      ...call,
      tableId: table.id,
      lookupColumnKey: resolveColumn(call.lookupColumnToken, previous?.lookupColumnKey).key,
      returnColumnKey: resolveColumn(call.returnColumnToken, previous?.returnColumnKey).key,
    };
  });
  return { expression, lookupRefs: dedupeRefs(refs) };
}

export async function buildFormulaLookupRegistry(refs: FormulaLookupRef[] = []): Promise<FormulaLookupRegistry> {
  const registry: FormulaLookupRegistry = {};
  const byTable = new Map<string, FormulaLookupRef[]>();
  for (const ref of refs) byTable.set(ref.tableId, [...(byTable.get(ref.tableId) ?? []), ref]);

  for (const [tableId, tableRefs] of byTable) {
    const rows = await db.select({ cells: gridRows.cells }).from(gridRows)
      .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId))).orderBy(asc(gridRows.position)).limit(MAX_LOOKUP_ROWS + 1);
    if (rows.length > MAX_LOOKUP_ROWS) throw new Error(`LOOKUP source table exceeds ${MAX_LOOKUP_ROWS.toLocaleString()} rows`);
    for (const ref of tableRefs) {
      const values: Record<string, unknown> = {};
      for (const row of rows) {
        const lookupValue = row.cells[ref.lookupColumnKey];
        // A blank key must match nothing: otherwise LOOKUP(..., blank, ...)
        // returns whatever the first blank-keyed row holds instead of the
        // default. With no entry, the sandbox falls through to the default/null.
        if (isBlankLookupKey(lookupValue)) continue;
        const key = lookupValueKey(lookupValue);
        if (!Object.prototype.hasOwnProperty.call(values, key)) values[key] = row.cells[ref.returnColumnKey] ?? null;
      }
      registry[formulaLookupSignature(ref.tableToken, ref.lookupColumnToken, ref.returnColumnToken)] = values;
    }
  }
  return registry;
}

export function formulaLookupSignature(table: string, lookupColumn: string, returnColumn: string): string {
  return JSON.stringify([table.trim().toLowerCase(), lookupColumn.trim().toLowerCase(), returnColumn.trim().toLowerCase()]);
}

export function isBlankLookupKey(value: unknown): boolean {
  return value === null || value === undefined || (typeof value === "string" && value.trim() === "");
}

function lookupValueKey(value: unknown): string {
  return `${value === null ? "null" : typeof value}:${JSON.stringify(value ?? null)}`;
}

export function parseLookupCalls(expression: string): ParsedLookup[] {
  const calls: ParsedLookup[] = [];
  const pattern = /\bLOOKUP\s*\(/gi;
  for (const match of expression.matchAll(pattern)) {
    const start = (match.index ?? 0) + match[0].length;
    const { args } = readArguments(expression, start);
    if (args.length < 4 || args.length > 5) throw new Error("LOOKUP expects 4 arguments and an optional default value");
    calls.push({
      tableToken: stringLiteral(args[0], "table"),
      lookupColumnToken: stringLiteral(args[2], "lookup column"),
      returnColumnToken: stringLiteral(args[3], "return column"),
    });
  }
  return calls;
}

function readArguments(source: string, start: number): { args: string[]; end: number } {
  const args: string[] = [];
  let quote = "";
  let escaped = false;
  let depth = 0;
  let current = "";
  for (let index = start; index < source.length; index += 1) {
    const char = source[index];
    if (quote) {
      current += char;
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === quote) quote = "";
      continue;
    }
    if (char === '"' || char === "'") { quote = char; current += char; continue; }
    if (char === "(" || char === "[" || char === "{") { depth += 1; current += char; continue; }
    if (char === ")") {
      if (depth === 0) { args.push(current.trim()); return { args, end: index }; }
      depth -= 1; current += char; continue;
    }
    if (char === "]" || char === "}") { depth -= 1; current += char; continue; }
    if (char === "," && depth === 0) { args.push(current.trim()); current = ""; continue; }
    current += char;
  }
  throw new Error("LOOKUP is missing a closing parenthesis");
}

function stringLiteral(value: string, label: string): string {
  const trimmed = value.trim();
  if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
    try { return JSON.parse(trimmed); } catch { /* handled below */ }
  }
  if (trimmed.startsWith("'") && trimmed.endsWith("'")) {
    return trimmed.slice(1, -1).replace(/\\'/g, "'").replace(/\\\\/g, "\\");
  }
  throw new Error(`LOOKUP ${label} must be a quoted name, key, or ID`);
}

function dedupeRefs(refs: FormulaLookupRef[]): FormulaLookupRef[] {
  return [...new Map(refs.map((ref) => [formulaLookupSignature(ref.tableToken, ref.lookupColumnToken, ref.returnColumnToken), ref])).values()];
}

const TEXT_LIKE = new Set(["text", "url", "email", "select", "image"]);

/**
 * Keys of the table's text-like columns. A formula sees a blank one as "" —
 * the way a spreadsheet does — so `{{first}} + " " + {{last}}` with no last
 * name gives "Ada ", not "Ada null". Blank numbers, dates and JSON stay null.
 */
export async function textColumnKeys(tableId: string): Promise<Set<string>> {
  const columns = await db
    .select({ key: gridColumns.key, type: gridColumns.type, config: gridColumns.config })
    .from(gridColumns)
    .where(and(inOrgTables(gridColumns.tableId), eq(gridColumns.tableId, tableId)));
  return new Set(
    columns.filter((column) => TEXT_LIKE.has(effectiveColumnType(column as never))).map((column) => column.key),
  );
}
