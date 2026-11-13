import { and, asc, count, countDistinct, desc, eq, isNull, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import {
  gridColumns,
  gridFolders,
  gridRows,
  gridTables,
  gridWorkbooks,
  type GridTable,
  type GridWorkbook,
} from "./schema";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";

export type WorkbookSummary = GridWorkbook & { tableCount: number; rowCount: number };

/**
 * Table and row counts per workbook, as a joinable derived table.
 *
 * These used to be correlated scalar subqueries, and they always read 0.
 * Drizzle renders a column reference inside a raw `sql` template WITHOUT its
 * table qualifier, so `WHERE ${gridTables.workbookId} = ${gridWorkbooks.id}`
 * became `WHERE "workbook_id" = "id"` — and inside the subquery, bare "id"
 * binds to grid_tables.id, not the outer grid_workbooks.id. The predicate
 * compared a table's workbook_id to its own id, matched nothing, and every
 * workbook reported "0 tables · 0 rows". A join carries proper aliases, so
 * there is nothing left to shadow.
 *
 * countDistinct on the table id is required because the LEFT JOIN to rows
 * fans each table out to one output row per grid row.
 */
function workbookCounts() {
  return db
    .select({
      workbookId: gridTables.workbookId,
      tableCount: countDistinct(gridTables.id).as("table_count"),
      rowCount: count(gridRows.id).as("row_count"),
    })
    .from(gridTables)
    .leftJoin(gridRows, eq(gridRows.tableId, gridTables.id))
    .where(inOrg(gridTables))
    .groupBy(gridTables.workbookId)
    .as("workbook_counts");
}

/**
 * Workbooks filed directly in `folderId` (NULL = the root of All Files), or
 * every workbook when `folderId` is `"all"`.
 */
export async function listWorkbooks(
  folderId: string | null | "all" = "all",
): Promise<WorkbookSummary[]> {
  const counts = workbookCounts();

  const query = db
    .select({
      id: gridWorkbooks.id,
      organizationId: gridWorkbooks.organizationId,
      name: gridWorkbooks.name,
      description: gridWorkbooks.description,
      folderId: gridWorkbooks.folderId,
      createdAt: gridWorkbooks.createdAt,
      updatedAt: gridWorkbooks.updatedAt,
      tableCount: counts.tableCount,
      rowCount: counts.rowCount,
    })
    .from(gridWorkbooks)
    .leftJoin(counts, eq(counts.workbookId, gridWorkbooks.id))
    .$dynamic();

  query.where(
    folderId === "all"
      ? inOrg(gridWorkbooks)
      : and(
          inOrg(gridWorkbooks),
          folderId === null ? isNull(gridWorkbooks.folderId) : eq(gridWorkbooks.folderId, folderId),
        ),
  );

  const rows = await query.orderBy(desc(gridWorkbooks.updatedAt));

  // The LEFT JOIN leaves NULL for a workbook with no tables. Coalescing here
  // rather than in a `sql` template keeps this away from the unqualified-
  // reference problem described above.
  return rows.map((row) => ({
    ...row,
    tableCount: Number(row.tableCount ?? 0),
    rowCount: Number(row.rowCount ?? 0),
  }));
}

export async function getWorkbook(id: string): Promise<GridWorkbook | null> {
  const [row] = await db.select().from(gridWorkbooks).where(and(inOrg(gridWorkbooks), eq(gridWorkbooks.id, id))).limit(1);
  return row ?? null;
}

/** Sheet tabs, in tab order. */
export async function listWorkbookTables(workbookId: string): Promise<GridTable[]> {
  return db
    .select()
    .from(gridTables)
    .where(and(inOrg(gridTables), eq(gridTables.workbookId, workbookId)))
    .orderBy(asc(gridTables.position));
}

/**
 * A new workbook is never empty — it opens with one table, one column and a
 * few blank rows, because an empty grid gives the user nothing to click.
 */
export async function createWorkbook(input: {
  name: string;
  firstTableName?: string;
  /** NULL/omitted files the workbook at the root of All Files. */
  folderId?: string | null;
}): Promise<{ workbook: GridWorkbook; table: GridTable }> {
  return db.transaction(async (tx) => {
    // A stale folder id from a tab left open on a deleted folder would fail
    // the FK and lose the whole workbook; drop it to the root instead.
    let folderId: string | null = null;
    if (input.folderId) {
      const [folder] = await tx
        .select({ id: gridFolders.id })
        .from(gridFolders)
        .where(and(inOrg(gridFolders), eq(gridFolders.id, input.folderId)))
        .limit(1);
      folderId = folder?.id ?? null;
    }

    const [workbook] = await tx
      .insert(gridWorkbooks)
      .values({ organizationId: currentOrganizationId(), name: input.name.trim() || "Untitled workbook", folderId })
      .returning();

    const [table] = await tx
      .insert(gridTables)
      .values({
        organizationId: currentOrganizationId(),
        workbookId: workbook.id,
        name: input.firstTableName?.trim() || "Custom Table",
        position: 1,
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

    return { workbook, table };
  });
}

export async function updateWorkbook(
  id: string,
  patch: { name?: string; description?: string | null; folderId?: string | null },
): Promise<GridWorkbook | null> {
  const values: Record<string, unknown> = { updatedAt: new Date() };
  if (patch.name !== undefined) values.name = patch.name.trim();
  if (patch.description !== undefined) values.description = patch.description;

  if (patch.folderId !== undefined) {
    if (patch.folderId !== null) {
      const [folder] = await db
        .select({ id: gridFolders.id })
        .from(gridFolders)
        .where(and(inOrg(gridFolders), eq(gridFolders.id, patch.folderId)))
        .limit(1);
      if (!folder) throw new Error("That destination folder no longer exists");
    }
    values.folderId = patch.folderId;
  }

  const [row] = await db
    .update(gridWorkbooks)
    .set(values)
    .where(and(inOrg(gridWorkbooks), eq(gridWorkbooks.id, id)))
    .returning();
  return row ?? null;
}

/** Cascades through tables, columns, rows, jobs and cell runs. */
export async function deleteWorkbook(id: string): Promise<boolean> {
  const deleted = await db
    .delete(gridWorkbooks)
    .where(and(inOrg(gridWorkbooks), eq(gridWorkbooks.id, id)))
    .returning({ id: gridWorkbooks.id });
  return deleted.length > 0;
}
