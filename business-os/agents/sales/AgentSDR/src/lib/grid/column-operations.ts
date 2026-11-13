import { and, asc, eq, inArray, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { gridColumns, gridRows, type GridColumn } from "./schema";
import { uniqueColumnKey } from "./columns";
import { inOrgTables } from "./scope";
import { gridTables } from "./schema";
import { currentOrganizationId } from "@/lib/tenancy/scope";
import { effectiveColumnType } from "./value-types";

export const TEXT_SPLIT_DELIMITERS = ["comma", "space", "semicolon", "pipe"] as const;
export type TextSplitDelimiter = (typeof TEXT_SPLIT_DELIMITERS)[number];

function splitValue(value: unknown, delimiter: TextSplitDelimiter): string[] {
  if (value === undefined || value === null || String(value).trim() === "") return [];
  const raw = String(value);
  const parts = delimiter === "space"
    ? raw.trim().split(/\s+/)
    : raw.split(delimiter === "comma" ? "," : delimiter === "semicolon" ? ";" : "|");
  return parts.map((part) => part.trim());
}

/**
 * Splits one text column into new static text columns immediately to its right.
 * The original is intentionally retained so this transformation is lossless.
 */
export async function splitTextColumn(
  tableId: string,
  columnId: string,
  delimiter: TextSplitDelimiter,
): Promise<{ columns: GridColumn[]; rowsUpdated: number }> {
  return db.transaction(async (tx) => {
    const [source] = await tx
      .select()
      .from(gridColumns)
      .where(and(inOrgTables(gridColumns.tableId), eq(gridColumns.id, columnId), eq(gridColumns.tableId, tableId)))
      .limit(1)
      .for("update");
    if (!source) throw new Error("column not found");
    if (effectiveColumnType(source) !== "text") {
      throw new Error("Text to columns is only available for text columns");
    }

    const [existing, rows] = await Promise.all([
      tx.select().from(gridColumns).where(and(inOrgTables(gridColumns.tableId), eq(gridColumns.tableId, tableId))).orderBy(asc(gridColumns.position)),
      tx.select({ id: gridRows.id, cells: gridRows.cells })
        .from(gridRows)
        .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId)))
        .orderBy(asc(gridRows.position))
        .for("update"),
    ]);
    const splitRows = rows.map((row) => ({ row, parts: splitValue(row.cells[source.key], delimiter) }));
    const outputCount = Math.max(0, ...splitRows.map(({ parts }) => parts.length));
    if (outputCount < 2) throw new Error("No values in this column contain that separator");
    if (outputCount > 100) throw new Error("Text to columns can create at most 100 columns at a time");
    if (rows.length * outputCount > 50_000) {
      throw new Error("Text to columns is limited to 50,000 output cells at a time");
    }

    const sourceIndex = existing.findIndex((column) => column.id === source.id);
    const nextPosition = existing[sourceIndex + 1]?.position;
    const positionStep = nextPosition === undefined
      ? 1
      : (nextPosition - source.position) / (outputCount + 1);
    const takenKeys = new Set(existing.map((column) => column.key));
    const columnValues = Array.from({ length: outputCount }, (_, index) => {
      const name = `${source.name} ${index + 1}`;
      const key = uniqueColumnKey(name, takenKeys);
      takenKeys.add(key);
      return {
        tableId,
        key,
        name,
        type: "text" as const,
        config: {},
        autoRun: false,
        dependsOn: [],
        position: source.position + positionStep * (index + 1),
      };
    });
    const created = await tx.insert(gridColumns).values(columnValues).returning();

    const patches = splitRows.map(({ row, parts }) => ({
      rowId: row.id,
      patch: Object.fromEntries(created.map((column, index) => [column.key, parts[index] || null])),
    }));
    const chunkSize = 250;
    let rowsUpdated = 0;
    for (let offset = 0; offset < patches.length; offset += chunkSize) {
      const chunk = patches.slice(offset, offset + chunkSize);
      const values = sql.join(
        chunk.map(({ rowId, patch }) => sql`(${rowId}::uuid, ${JSON.stringify(patch)}::jsonb)`),
        sql`, `,
      );
      const updated = await tx.execute<{ id: string }>(sql`
        UPDATE ${gridRows}
        SET
          cells = ${gridRows.cells} || source.patch,
          version = nextval('grid_row_version_seq'),
          updated_at = now()
        FROM (VALUES ${values}) AS source(id, patch)
        WHERE ${gridRows.id} = source.id
          AND ${gridRows.tableId} = ${tableId}::uuid
          AND ${gridRows.tableId} IN (SELECT id FROM ${gridTables} WHERE organization_id = ${currentOrganizationId()})
        RETURNING ${gridRows.id} AS id
      `);
      rowsUpdated += updated.length;
    }

    return { columns: created, rowsUpdated };
  });
}

/** Removes duplicate rows by exact non-empty value, keeping the first row. */
export async function dedupeRowsByColumn(
  tableId: string,
  columnId: string,
): Promise<number> {
  return db.transaction(async (tx) => {
    const [column] = await tx
      .select()
      .from(gridColumns)
      .where(and(inOrgTables(gridColumns.tableId), eq(gridColumns.id, columnId), eq(gridColumns.tableId, tableId)))
      .limit(1)
      .for("update");
    if (!column) throw new Error("column not found");

    const rows = await tx
      .select({ id: gridRows.id, cells: gridRows.cells })
      .from(gridRows)
      .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId)))
      .orderBy(asc(gridRows.position))
      .for("update");
    const seen = new Set<string>();
    const duplicateIds: string[] = [];
    for (const row of rows) {
      const value = row.cells[column.key];
      if (value === undefined || value === null || (typeof value === "string" && value.trim() === "")) continue;
      const identity = `${typeof value}:${JSON.stringify(value)}`;
      if (seen.has(identity)) duplicateIds.push(row.id);
      else seen.add(identity);
    }
    if (!duplicateIds.length) return 0;

    const deleted = await tx
      .delete(gridRows)
      .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId), inArray(gridRows.id, duplicateIds)))
      .returning({ id: gridRows.id });
    return deleted.length;
  });
}
