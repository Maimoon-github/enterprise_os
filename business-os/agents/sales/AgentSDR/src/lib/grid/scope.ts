import { and, eq, inArray, type Column } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { gridTables } from "./schema";

/**
 * grid_columns, grid_rows, grid_jobs and grid_cell_runs carry no
 * organization of their own; they inherit it through table_id. Filtering a
 * child by `inOrgTables(child.tableId)` keeps another organization's table id
 * reading as "not found", and is what every child query below adds beside
 * its table_id / id predicate.
 */
export function inOrgTables(tableIdColumn: Column) {
  return inArray(tableIdColumn, db.select({ id: gridTables.id }).from(gridTables).where(inOrg(gridTables)));
}

/** Whether `tableId` is one of the current organization's tables. */
export async function tableInOrganization(tableId: string): Promise<boolean> {
  const [row] = await db
    .select({ id: gridTables.id })
    .from(gridTables)
    .where(and(inOrg(gridTables), eq(gridTables.id, tableId)))
    .limit(1);
  return Boolean(row);
}
