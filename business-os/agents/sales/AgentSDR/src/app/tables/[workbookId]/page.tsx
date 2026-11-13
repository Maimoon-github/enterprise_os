import { requirePageOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";
import { notFound } from "next/navigation";
import GridLoader from "@/components/grid/GridLoader";
import { listColumns } from "@/lib/grid/columns";
import { effectiveColumnType } from "@/lib/grid/value-types";
import { countRows, currentVersion, listRows } from "@/lib/grid/rows";
import { columnCoverage } from "@/lib/grid/tables";
import { folderPath } from "@/lib/grid/folders";
import { activeJobCount } from "@/lib/grid/queue";
import { getWorkbook, listWorkbookTables } from "@/lib/grid/workbooks";
import { GRID_PAGE_SIZE } from "@/lib/grid/pagination";
import { sanitizeView, type FilterGroup, type SortSpec } from "@/lib/grid/query";

export const dynamic = "force-dynamic";

export default async function WorkbookPage({
  params,
  searchParams,
}: {
  params: Promise<{ workbookId: string }>;
  searchParams: Promise<{ table?: string }>;
}) {
  const ctx = await requirePageOrgContext();
  return runInOrganization(ctx.organizationId, async () => {
    const { workbookId } = await params;
    const { table: requestedTableId } = await searchParams;

    // Both keyed off workbookId alone — nothing is gained by waiting for the
    // workbook row before asking for its tabs, and every serial query here is a
    // round trip the user watches a blank page for.
    const [workbook, tables] = await Promise.all([
      getWorkbook(workbookId),
      listWorkbookTables(workbookId),
    ]);
    if (!workbook) notFound();
    if (!tables.length) notFound();

    // ?table= wins so a refresh or shared link reopens the same sheet; an id
    // that no longer exists falls back to the first tab rather than 404ing.
    const active = tables.find((t) => t.id === requestedTableId) ?? tables[0];

    const [columns, breadcrumbs] = await Promise.all([
      listColumns(active.id),
      folderPath(workbook.folderId),
    ]);
    // Drops sorts/filters on columns deleted since the view was saved, as the
    // table API does, so the grid never starts from a view it cannot save.
    const view = sanitizeView(active.view, new Set(columns.map((c) => c.key)));
    const refs = columns.map((c) => ({ key: c.key, type: effectiveColumnType(c) }));
    const query = { filters: view.filters as FilterGroup | undefined, sorts: view.sorts as SortSpec[] | undefined };

    const [rows, total, unfilteredTotal, cursor, coverage, activeJobs] = await Promise.all([
      listRows(active.id, { limit: GRID_PAGE_SIZE, query, columns: refs }),
      countRows(active.id, { query, columns: refs }),
      countRows(active.id),
      currentVersion(active.id),
      columnCoverage(active.id, columns),
      activeJobCount(active.id),
    ]);

    return (
      <div className="h-full flex overflow-hidden bg-bg-white-0">
        <div className="min-w-0 flex-1 overflow-hidden">
          <GridLoader
            workbook={workbook}
            tables={tables}
            breadcrumbs={breadcrumbs}
            initialSheet={{ table: active, columns, rows, total, unfilteredTotal, cursor, coverage, activeJobs, view }}
          />
        </div>
      </div>
    );
  });
}
