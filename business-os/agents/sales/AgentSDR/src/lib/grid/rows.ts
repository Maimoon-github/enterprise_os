import { and, asc, count, eq, gt, inArray, or, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrgTables, tableInOrganization } from "./scope";
import { gridJobs, gridRows, gridTables, type GridRow } from "./schema";
import { currentOrganizationId } from "@/lib/tenancy/scope";
import type { CellMeta, CellValues, ColumnType } from "./types";
import { reconcileIdleTable } from "./queue";
import { assertKnownColumns, buildOrderBy, buildWhere, type GridQuery } from "./query";

/** Bumps the global version so pollers see the write. Always set on update. */
const NEXT_VERSION = sql`nextval('grid_row_version_seq')`;

export type ColumnRef = { key: string; type: ColumnType };

/**
 * Rows for a table, optionally filtered, searched and sorted.
 *
 * `columns` is required whenever `query` narrows anything: the builder needs
 * each column's type to know whether to compare numerically or as text, and
 * to reject a filter naming a column that no longer exists.
 */
export async function listRows(
  tableId: string,
  opts: { limit?: number; offset?: number; query?: GridQuery; columns?: ColumnRef[] } = {},
): Promise<GridRow[]> {
  const columns = opts.columns ?? [];
  const query = opts.query ?? {};

  if (opts.query) assertKnownColumns(query, new Set(columns.map((c) => c.key)));
  const extra = opts.query ? buildWhere(query, columns) : null;

  return db
    .select()
    .from(gridRows)
    .where(extra ? and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId), extra) : and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId)))
    .orderBy(opts.query ? buildOrderBy(query.sorts, columns) : asc(gridRows.position))
    .limit(Math.min(opts.limit ?? 200, 1000))
    .offset(opts.offset ?? 0);
}

/** Fetches explicitly selected rows without depending on their table position. */
export async function listRowsByIds(tableId: string, rowIds: string[]): Promise<GridRow[]> {
  if (!rowIds.length) return [];
  return db
    .select()
    .from(gridRows)
    .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId), inArray(gridRows.id, [...new Set(rowIds)])))
    .orderBy(asc(gridRows.position));
}

/**
 * IDs for every row matching a saved view and optional transient search.
 *
 * Selection is intentionally query-scoped instead of relying on AG Grid's
 * loaded page: a table can contain up to 50k rows while the browser only has
 * one 200-row page at a time.
 */
export async function listRowIds(
  tableId: string,
  opts: { query?: GridQuery; columns?: ColumnRef[] } = {},
): Promise<string[]> {
  const columns = opts.columns ?? [];
  const query = opts.query ?? {};

  if (opts.query) assertKnownColumns(query, new Set(columns.map((c) => c.key)));
  const extra = opts.query ? buildWhere(query, columns) : null;
  const rows = await db
    .select({ id: gridRows.id })
    .from(gridRows)
    .where(extra ? and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId), extra) : and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId)))
    .orderBy(opts.query ? buildOrderBy(query.sorts, columns) : asc(gridRows.position));

  return rows.map((row) => row.id);
}

/** Total rows in the table, or matching `query` when one is given. */
export async function countRows(
  tableId: string,
  opts: { query?: GridQuery; columns?: ColumnRef[] } = {},
): Promise<number> {
  const columns = opts.columns ?? [];
  const extra = opts.query ? buildWhere(opts.query, columns) : null;

  const [row] = await db
    .select({ n: count() })
    .from(gridRows)
    .where(extra ? and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId), extra) : and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId)));
  return row?.n ?? 0;
}

/** Highest position in the table — the append point. */
async function maxPosition(tableId: string): Promise<number> {
  const [row] = await db
    .select({ max: sql<number | null>`max(${gridRows.position})` })
    .from(gridRows)
    .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId)));
  return row?.max ?? 0;
}

/** Appends blank rows — the "+ Add N more rows at the bottom" control. */
export async function addBlankRows(tableId: string, n: number): Promise<GridRow[]> {
  if (!(await tableInOrganization(tableId))) throw new Error("That table no longer exists");
  const howMany = Math.max(1, Math.min(n, 1000));
  const start = await maxPosition(tableId);
  return db
    .insert(gridRows)
    .values(
      Array.from({ length: howMany }, (_, i) => ({
        tableId,
        position: start + i + 1,
        cells: {},
        cellMeta: {},
        version: NEXT_VERSION as unknown as number,
      })),
    )
    .returning();
}

/**
 * Bulk insert with data — the CSV/XLSX import path.
 *
 * Chunked because a single INSERT with tens of thousands of rows blows past
 * Postgres' bind-parameter limit; 500 keeps each statement well inside it.
 */
export async function insertRows(tableId: string, records: CellValues[]): Promise<number> {
  if (!records.length) return 0;
  if (!(await tableInOrganization(tableId))) throw new Error("That table no longer exists");
  const start = await maxPosition(tableId);
  const CHUNK = 500;
  let inserted = 0;

  for (let i = 0; i < records.length; i += CHUNK) {
    const chunk = records.slice(i, i + CHUNK);
    await db.insert(gridRows).values(
      chunk.map((cells, j) => ({
        tableId,
        position: start + i + j + 1,
        cells,
        cellMeta: {},
        version: NEXT_VERSION as unknown as number,
      })),
    );
    inserted += chunk.length;
  }

  return inserted;
}

/**
 * Writes one cell value.
 *
 * Uses the `||` merge operator rather than jsonb_set because it adds the key
 * when absent without needing create_missing, and reads the same for both
 * cases.
 */
export async function setCellValue(
  tableId: string,
  rowId: string,
  columnKey: string,
  value: unknown,
): Promise<GridRow | null> {
  const patch = JSON.stringify({ [columnKey]: value ?? null });
  const [row] = await db
    .update(gridRows)
    .set({
      cells: sql`${gridRows.cells} || ${patch}::jsonb`,
      version: NEXT_VERSION,
      updatedAt: new Date(),
    })
    .where(and(inOrgTables(gridRows.tableId), eq(gridRows.id, rowId), eq(gridRows.tableId, tableId)))
    .returning();
  return row ?? null;
}

export type CellValueUpdate = {
  rowId: string;
  columnKey: string;
  value: unknown;
};

/**
 * Writes a spreadsheet-sized batch of cell values while bumping each touched
 * row only once. The table predicate is important here: clipboard payloads are
 * client supplied, so an ID from another table must never be writable.
 */
export async function setCellValues(
  tableId: string,
  updates: CellValueUpdate[],
): Promise<{ updatedRows: number; previousValues: CellValueUpdate[] }> {
  if (!updates.length) return { updatedRows: 0, previousValues: [] };

  const patches = new Map<string, Record<string, unknown>>();
  for (const update of updates) {
    const patch = patches.get(update.rowId) ?? {};
    patch[update.columnKey] = update.value ?? null;
    patches.set(update.rowId, patch);
  }

  return db.transaction(async (tx) => {
    let updated = 0;
    // A stable lock order prevents two overlapping clipboard writes from
    // deadlocking when their selections were dragged in opposite directions.
    const orderedPatches = [...patches.entries()].sort(([left], [right]) => left.localeCompare(right));
    const lockedRows = await tx
      .select({ id: gridRows.id, cells: gridRows.cells })
      .from(gridRows)
      .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId), inArray(gridRows.id, orderedPatches.map(([rowId]) => rowId))))
      .orderBy(asc(gridRows.id))
      .for("update");
    if (lockedRows.length !== orderedPatches.length) {
      throw new Error("one or more rows were not found in this table");
    }
    const previousByRow = new Map(lockedRows.map((row) => [row.id, row.cells]));
    const previousValues = updates.map((update) => ({
      rowId: update.rowId,
      columnKey: update.columnKey,
      value: previousByRow.get(update.rowId)?.[update.columnKey] ?? null,
    }));

    const CHUNK = 250;
    for (let offset = 0; offset < orderedPatches.length; offset += CHUNK) {
      const chunk = orderedPatches.slice(offset, offset + CHUNK);
      const values = sql.join(
        chunk.map(([rowId, patch]) => sql`(${rowId}::uuid, ${JSON.stringify(patch)}::jsonb)`),
        sql`, `,
      );
      const rows = await tx.execute<{ id: string }>(sql`
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
      updated += rows.length;
    }
    if (updated !== patches.size) {
      throw new Error("one or more rows were not found in this table");
    }
    return { updatedRows: updated, previousValues };
  });
}

/** Writes the metadata plane for one cell — used by the worker, not the UI. */
export async function setCellMeta(
  rowId: string,
  columnKey: string,
  meta: CellMeta,
): Promise<void> {
  const patch = JSON.stringify({ [columnKey]: meta });
  await db
    .update(gridRows)
    .set({
      cellMeta: sql`${gridRows.cellMeta} || ${patch}::jsonb`,
      version: NEXT_VERSION,
      updatedAt: new Date(),
    })
    .where(and(inOrgTables(gridRows.tableId), eq(gridRows.id, rowId)));
}

export async function deleteRows(tableId: string, rowIds: string[]): Promise<number> {
  if (!rowIds.length) return 0;
  const deleted = await db
    .delete(gridRows)
    .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId), inArray(gridRows.id, rowIds)))
    .returning({ id: gridRows.id });
  return deleted.length;
}

/**
 * The re-read window behind the cursor. A version comes from nextval() when a
 * statement runs, but its row only becomes visible when the transaction
 * commits — so version 101 can appear after 102 is already visible, and a
 * strict `> cursor` would skip it for good.
 *
 * So a poll also re-reads rows within VERSION_OVERLAP versions behind the
 * cursor (versions are one global sequence; this must exceed the largest batch
 * one transaction writes, a 1,000-row paste), but only those written in the
 * last OVERLAP_SECONDS: a late commit is always recent, and without that bound
 * every poll during a run would re-send the last paste or import in full.
 * Every write that bumps `version` also sets `updated_at`. Rows seen twice are
 * harmless: the client overwrites by row id.
 */
const VERSION_OVERLAP = 2000;
const OVERLAP_SECONDS = 30;

/**
 * The polling endpoint's query: rows written since `cursor`.
 *
 * `activeJobs` is what tells the client whether to keep polling — when it
 * reaches zero the run is finished and the client can stop.
 */
export async function changesSince(
  tableId: string,
  cursor: number,
  limit = 500,
): Promise<{ rows: GridRow[]; cursor: number; activeJobs: number }> {
  const [jobs] = await db
    .select({ n: count() })
    .from(gridJobs)
    .where(
      and(
        inOrgTables(gridJobs.tableId),
        eq(gridJobs.tableId, tableId),
        inArray(gridJobs.status, ["queued", "running", "waiting"]),
      ),
    );

  // A table with no jobs left but cells still claiming to be queued or running
  // (a race or a crash left them) would spin forever: clear them first, so the
  // rows read below carry the cleanup. Throttled, and a no-op on a healthy table.
  const activeJobs = jobs?.n ?? 0;
  if (activeJobs === 0) await reconcileIdleTable(tableId);

  const rows = await db
    .select()
    .from(gridRows)
    .where(
      and(
        inOrgTables(gridRows.tableId),
        eq(gridRows.tableId, tableId),
        or(
          gt(gridRows.version, cursor),
          and(
            gt(gridRows.version, Math.max(0, cursor - VERSION_OVERLAP)),
            sql`${gridRows.updatedAt} > now() - make_interval(secs => ${OVERLAP_SECONDS})`,
          ),
        ),
      ),
    )
    .orderBy(asc(gridRows.version))
    // The overlap re-sends up to VERSION_OVERLAP rows already seen; leave room
    // for `limit` new ones so a busy table's cursor still advances.
    .limit(limit + VERSION_OVERLAP);

  return {
    rows,
    // Hold the cursor when nothing changed, and never move it backwards.
    cursor: rows.length ? Math.max(cursor, Number(rows[rows.length - 1].version)) : cursor,
    activeJobs,
  };
}

/** Current high-water mark, for a client opening the table fresh. */
export async function currentVersion(tableId: string): Promise<number> {
  const [row] = await db
    .select({ max: sql<number | null>`max(${gridRows.version})` })
    .from(gridRows)
    .where(and(inOrgTables(gridRows.tableId), eq(gridRows.tableId, tableId)));
  return Number(row?.max ?? 0);
}
