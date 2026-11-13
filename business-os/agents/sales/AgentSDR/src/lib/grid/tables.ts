import { and, asc, count, eq, gt, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { gridColumns, gridRows, gridTables, gridWorkbooks, type GridTable } from "./schema";
import { listWorkbookTables } from "./workbooks";
import type { TableView } from "./types";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";
import { inOrgTables } from "./scope";

export async function getTable(id: string): Promise<GridTable | null> {
  const [row] = await db.select().from(gridTables).where(and(inOrg(gridTables), eq(gridTables.id, id))).limit(1);
  return row ?? null;
}

/** Highest tab position in the workbook — where a new sheet is appended. */
async function maxTablePosition(workbookId: string): Promise<number> {
  const [row] = await db
    .select({ max: sql<number | null>`max(${gridTables.position})` })
    .from(gridTables)
    .where(and(inOrg(gridTables), eq(gridTables.workbookId, workbookId)));
  return row?.max ?? 0;
}

/**
 * Adds a sheet to a workbook. Seeded with one column and one row for the same
 * reason a new workbook is: an empty grid is a dead end for the user.
 */
export async function createTable(input: {
  workbookId: string;
  name?: string;
  description?: string;
}): Promise<GridTable> {
  const [workbook] = await db
    .select({ id: gridWorkbooks.id })
    .from(gridWorkbooks)
    .where(and(inOrg(gridWorkbooks), eq(gridWorkbooks.id, input.workbookId)))
    .limit(1);
  if (!workbook) throw new Error("That workbook no longer exists");

  const position = (await maxTablePosition(input.workbookId)) + 1;

  return db.transaction(async (tx) => {
    const [table] = await tx
      .insert(gridTables)
      .values({
        organizationId: currentOrganizationId(),
        workbookId: input.workbookId,
        name: input.name?.trim() || `Table ${Math.round(position)}`,
        description: input.description?.trim() || null,
        position,
      })
      .returning();

    await tx.insert(gridColumns).values({
      tableId: table.id,
      key: "name",
      name: "New Column",
      type: "text",
      config: {},
      dependsOn: [],
      position: 1,
    });

    await tx.insert(gridRows).values({
      tableId: table.id,
      position: 1,
      cells: {},
      cellMeta: {},
      version: sql<number>`nextval('grid_row_version_seq')`,
    });

    return table;
  });
}

export async function updateTable(
  id: string,
  patch: {
    name?: string;
    description?: string | null;
    autoRun?: boolean;
    view?: TableView;
  },
): Promise<GridTable | null> {
  const values: Record<string, unknown> = { updatedAt: new Date() };
  if (patch.name !== undefined) values.name = patch.name.trim();
  if (patch.description !== undefined) values.description = patch.description;
  if (patch.autoRun !== undefined) values.autoRun = patch.autoRun;
  // Replaced wholesale rather than merged: the client always sends the entire
  // view, and a merge would make removing the last filter impossible.
  if (patch.view !== undefined) values.view = patch.view;

  const [row] = await db.update(gridTables).set(values).where(and(inOrg(gridTables), eq(gridTables.id, id))).returning();
  return row ?? null;
}

/**
 * Moves a sheet into another workbook, appended as its last tab.
 *
 * Refuses to empty a workbook: WorkbookPage 404s when a workbook has no
 * tables, so moving out the last one would strand the user on a dead URL.
 * Columns, rows and queued jobs follow automatically — they hang off
 * table_id, which is not changing.
 */
export async function moveTable(id: string, destinationWorkbookId: string): Promise<GridTable> {
  const table = await getTable(id);
  if (!table) throw new Error("That table no longer exists");
  if (table.workbookId === destinationWorkbookId) return table;

  const [destination] = await db
    .select({ id: gridWorkbooks.id })
    .from(gridWorkbooks)
    .where(and(inOrg(gridWorkbooks), eq(gridWorkbooks.id, destinationWorkbookId)))
    .limit(1);
  if (!destination) throw new Error("That destination workbook no longer exists");

  const [{ n }] = await db
    .select({ n: count() })
    .from(gridTables)
    .where(and(inOrg(gridTables), eq(gridTables.workbookId, table.workbookId)));
  if (Number(n) <= 1) {
    throw new Error("A workbook must keep at least one table — duplicate it first");
  }

  const position = (await maxTablePosition(destinationWorkbookId)) + 1;
  const [moved] = await db
    .update(gridTables)
    .set({ workbookId: destinationWorkbookId, position, updatedAt: new Date() })
    .where(and(inOrg(gridTables), eq(gridTables.id, id)))
    .returning();
  return moved;
}

/**
 * Copies a sheet — its columns and every row's values and cell metadata —
 * into the same workbook, landing directly after the original.
 *
 * Rows are copied with INSERT … SELECT rather than read into the app and
 * written back: a table here can hold tens of thousands of rows, and pulling
 * that through Node to push it straight back would be pointless traffic.
 *
 * Queued jobs and cell run history are deliberately NOT copied. They describe
 * work in flight against the original's cells, not data the user authored, and
 * duplicating them would re-run and re-bill every pending enrichment.
 */
export async function duplicateTable(id: string): Promise<GridTable> {
  const source = await getTable(id);
  if (!source) throw new Error("That table no longer exists");

  return db.transaction(async (tx) => {
    // Sit between the source and whatever tab follows it, so the copy appears
    // next to its original instead of at the far end of the tab strip.
    const [next] = await tx
      .select({ position: gridTables.position })
      .from(gridTables)
      .where(
        and(
          inOrg(gridTables),
          eq(gridTables.workbookId, source.workbookId),
          gt(gridTables.position, source.position),
        ),
      )
      .orderBy(asc(gridTables.position))
      .limit(1);
    const position = next ? (source.position + next.position) / 2 : source.position + 1;

    const [copy] = await tx
      .insert(gridTables)
      .values({
        organizationId: currentOrganizationId(),
        workbookId: source.workbookId,
        name: `${source.name} (copy)`,
        description: source.description,
        autoRun: source.autoRun,
        view: source.view,
        position,
      })
      .returning();

    await tx.execute(sql`
      INSERT INTO ${gridColumns} (table_id, key, name, type, config, depends_on, position, auto_run)
      SELECT ${copy.id}, key, name, type, config, depends_on, position, auto_run
        FROM ${gridColumns} WHERE ${gridColumns.tableId} = ${source.id}
         AND ${gridColumns.tableId} IN (SELECT id FROM ${gridTables} WHERE organization_id = ${currentOrganizationId()})
    `);

    // Fresh version values from the shared sequence, not the source's: the
    // polling cursor is global, so reusing them would hide the new rows from
    // any client whose cursor already sits past them.
    await tx.execute(sql`
      INSERT INTO ${gridRows} (table_id, position, cells, cell_meta, version)
      SELECT ${copy.id}, position, cells,
             -- In-flight statuses describe jobs that are not copied, so they
             -- would spin in the copy forever. Finished and error states stay.
             (SELECT COALESCE(jsonb_object_agg(m.key, m.value), '{}'::jsonb)
                FROM jsonb_each(cell_meta) AS m
               WHERE COALESCE(m.value ->> 'status', '') NOT IN ('queued', 'running', 'processing')),
             nextval('grid_row_version_seq')
        FROM ${gridRows} WHERE ${gridRows.tableId} = ${source.id}
         AND ${gridRows.tableId} IN (SELECT id FROM ${gridTables} WHERE organization_id = ${currentOrganizationId()})
    `);

    return copy;
  });
}

/**
 * Rewrites tab order from a full list of ids — what a drag-and-drop drop
 * event produces. Ids not in the workbook are rejected rather than ignored,
 * so a stale client cannot silently reorder half the strip.
 */
export async function reorderTables(
  workbookId: string,
  orderedIds: string[],
): Promise<GridTable[]> {
  const existing = await db
    .select({ id: gridTables.id })
    .from(gridTables)
    .where(and(inOrg(gridTables), eq(gridTables.workbookId, workbookId)));

  const known = new Set(existing.map((t) => t.id));
  const requested = new Set(orderedIds);
  // Length alone is not enough: [a, b, b] against three tables passes a size
  // check while leaving one tab unpositioned and one written twice.
  if (
    requested.size !== orderedIds.length ||
    orderedIds.length !== known.size ||
    orderedIds.some((id) => !known.has(id))
  ) {
    throw new Error("That tab order no longer matches the workbook");
  }

  await db.transaction(async (tx) => {
    for (const [index, id] of orderedIds.entries()) {
      await tx
        .update(gridTables)
        .set({ position: index + 1, updatedAt: new Date() })
        .where(and(inOrg(gridTables), eq(gridTables.id, id)));
    }
  });

  return listWorkbookTables(workbookId);
}

/**
 * Refusal to delete a workbook's only table (the DELETE route answers 409):
 * WorkbookPage 404s on a workbook with no tables.
 */
export class LastTableError extends Error {
  constructor() {
    super("A workbook must keep at least one table — delete the workbook instead");
    this.name = "LastTableError";
  }
}

/** Columns, rows, jobs and cell runs all cascade from the FK. */
export async function deleteTable(id: string): Promise<boolean> {
  const table = await getTable(id);
  if (!table) return false;

  return db.transaction(async (tx) => {
    // Lock the workbook so two tabs deleted at once cannot both see a sibling.
    await tx
      .select({ id: gridWorkbooks.id })
      .from(gridWorkbooks)
      .where(and(inOrg(gridWorkbooks), eq(gridWorkbooks.id, table.workbookId)))
      .for("update");
    const [{ n }] = await tx
      .select({ n: count() })
      .from(gridTables)
      .where(and(inOrg(gridTables), eq(gridTables.workbookId, table.workbookId)));
    if (Number(n) <= 1) throw new LastTableError();

    const deleted = await tx
      .delete(gridTables)
      .where(and(inOrg(gridTables), eq(gridTables.id, id)))
      .returning({ id: gridTables.id });
    return deleted.length > 0;
  });
}

/**
 * Per-column fill rate, as a percentage of rows holding a non-empty value.
 *
 * This is what the "%" row above the first data row reports. Computed in
 * Postgres rather than over the fetched page, because the page is only the
 * first 200 rows and a coverage figure for 200 of 40,000 rows would be
 * actively misleading.
 *
 * `known` lets a caller that already holds the column list hand it over. The
 * whole thing then costs one round trip instead of three, which is most of
 * what a tab switch was waiting on — every extra trip to the database is a
 * full SSL round trip to a remote host.
 */
export async function columnCoverage(
  tableId: string,
  known?: { key: string }[],
): Promise<Record<string, number>> {
  const columns = known ?? await db
    .select({ key: gridColumns.key })
    .from(gridColumns)
    .where(and(inOrgTables(gridColumns.tableId), eq(gridColumns.tableId, tableId)))
    .orderBy(asc(gridColumns.position));

  if (!columns.length) return {};

  // One pass, one aggregate per column, rather than a query per column. The
  // row total rides along in the same pass — it used to be its own query, and
  // it is scanning exactly the same rows.
  //
  // Each aggregate needs an explicit alias: without one Postgres names them
  // all "count", they collapse into a single key on the returned row object,
  // and every column but the first reads back as undefined.
  const filledExpr = sql.join(
    columns.map(
      (c, i) =>
        sql`count(*) FILTER (
          WHERE ${gridRows.cells} ->> ${c.key} IS NOT NULL
            AND ${gridRows.cells} ->> ${c.key} <> ''
        )::int AS ${sql.identifier(`c${i}`)}`,
    ),
    sql`, `,
  );

  const result = await db.execute<Record<string, number>>(
    sql`SELECT count(*)::int AS total, ${filledExpr} FROM ${gridRows} WHERE ${gridRows.tableId} = ${tableId}
      AND ${gridRows.tableId} IN (SELECT id FROM ${gridTables} WHERE organization_id = ${currentOrganizationId()})`,
  );

  // db.ts uses the postgres-js driver, whose execute() resolves to the rows
  // array itself rather than a { rows } wrapper.
  const first: Record<string, number> = result[0] ?? {};
  const total = Number(first.total) || 0;
  if (!total) return Object.fromEntries(columns.map((c) => [c.key, 0]));

  return Object.fromEntries(
    columns.map((c, i) => [c.key, Math.round(((Number(first[`c${i}`]) || 0) / total) * 100)]),
  );
}
