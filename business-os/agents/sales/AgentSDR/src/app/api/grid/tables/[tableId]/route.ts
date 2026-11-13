import { NextRequest, NextResponse } from "next/server";
import { columnCoverage, deleteTable, getTable, LastTableError, moveTable, updateTable } from "@/lib/grid/tables";
import { listColumns } from "@/lib/grid/columns";
import { countRows, currentVersion, listRows } from "@/lib/grid/rows";
import { activeJobCount } from "@/lib/grid/queue";
import { sanitizeView, validateView, type GridQuery } from "@/lib/grid/query";
import type { TableView } from "@/lib/grid/types";
import { effectiveColumnType } from "@/lib/grid/value-types";
import { GRID_PAGE_SIZE } from "@/lib/grid/pagination";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { clientMessage, intParam, isRecord, isUuid, nullableUuid, optionalName } from "@/lib/grid/validate";

/**
 * GET /api/grid/tables/[tableId]
 *
 * Returns the table, its columns, and a page of rows with the table's saved
 * view (filters and sorts) applied. `?search=` narrows further and is NOT
 * saved — a search is a transient lookup, whereas filters and sorts are part
 * of the view and persist for whoever opens the table next.
 *
 * `total` is the filtered count; `unfilteredTotal` is the whole table, so the
 * toolbar can honestly say "12/400 rows".
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(req, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId)) return NextResponse.json({ error: "not found" }, { status: 404 });

      const limit = intParam(req.nextUrl.searchParams.get("limit"), GRID_PAGE_SIZE, { min: 1, max: 1000 });
      const offset = intParam(req.nextUrl.searchParams.get("offset"), 0);
      if (limit === null || offset === null) {
        return NextResponse.json({ error: "limit and offset must be whole numbers" }, { status: 400 });
      }
      const search = req.nextUrl.searchParams.get("search") ?? undefined;

      // Fetched together: the column list is keyed off tableId alone, so waiting
      // for the table row first only bought an extra serial round trip on a path
      // the user sits and watches every time they switch tabs.
      const [table, columns] = await Promise.all([getTable(tableId), listColumns(tableId)]);
      if (!table) return NextResponse.json({ error: "not found" }, { status: 404 });

      const refs = columns.map((c) => ({ key: c.key, type: effectiveColumnType(c) }));

      // A saved view outlives the columns it names (or may predate validation
      // on save): whatever the table can no longer apply is dropped here
      // instead of failing every read of the table.
      const view = sanitizeView(table.view, new Set(columns.map((c) => c.key)));
      const query: GridQuery = {
        filters: view.filters as GridQuery["filters"],
        sorts: view.sorts as GridQuery["sorts"],
        search: search || undefined,
      };

      try {
        const [rows, total, unfilteredTotal, cursor, coverage, activeJobs] = await Promise.all([
          listRows(tableId, { limit, offset, query, columns: refs }),
          countRows(tableId, { query, columns: refs }),
          countRows(tableId),
          currentVersion(tableId),
          columnCoverage(tableId, columns),
          activeJobCount(tableId),
        ]);

        return NextResponse.json({
          table,
          columns,
          rows,
          total,
          unfilteredTotal,
          cursor,
          coverage,
          activeJobs,
          view,
        });
      } catch (err) {
        // The saved view is sanitized above, so a failure here is not the
        // caller's input; keep the database's message out of the response.
        console.error("grid table read failed", err);
        return NextResponse.json({ error: "could not read rows" }, { status: 500 });
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

// PATCH /api/grid/tables/[tableId]
//   { name?, description?, autoRun?, view?, workbookId? }
//
// `workbookId` moves the sheet to another workbook and is applied first, so a
// combined rename-and-move does not half-apply if the move is rejected.
export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(req, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId)) return NextResponse.json({ error: "not found" }, { status: 404 });

      let body: Record<string, unknown>;
      try {
        const parsed = await req.json();
        if (!isRecord(parsed)) throw new Error("not an object");
        body = parsed;
      } catch {
        return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
      }

      const badRequest = (error: string) => NextResponse.json({ error }, { status: 400 });
      const name = optionalName(body.name);
      if (!name.ok) return badRequest(name.error);
      const workbook = nullableUuid(body.workbookId, "workbookId");
      if (!workbook.ok || workbook.value === null) return badRequest(workbook.ok ? "workbookId cannot be null" : workbook.error);
      if (body.description !== undefined && body.description !== null && typeof body.description !== "string") {
        return badRequest("description must be text");
      }
      if (body.autoRun !== undefined && typeof body.autoRun !== "boolean") return badRequest("autoRun must be true or false");

      const fields: { name?: string; description?: string | null; autoRun?: boolean; view?: TableView } = {};
      if (name.value !== undefined) fields.name = name.value;
      if (body.description !== undefined) fields.description = body.description as string | null;
      if (body.autoRun !== undefined) fields.autoRun = body.autoRun as boolean;
      if (body.view !== undefined) {
        if (!(await getTable(tableId))) return NextResponse.json({ error: "not found" }, { status: 404 });
        const columns = await listColumns(tableId);
        const problem = validateView(body.view, new Set(columns.map((c) => c.key)));
        if (problem) return badRequest(problem);
        fields.view = body.view as TableView;
      }

      try {
        let table = workbook.value ? await moveTable(tableId, workbook.value) : null;

        if (Object.keys(fields).length > 0) {
          table = await updateTable(tableId, fields);
        }
        if (!table) return NextResponse.json({ error: "not found" }, { status: 404 });
        return NextResponse.json({ table });
      } catch (cause) {
        // moveTable rejects a dead destination and emptying a workbook.
        const message = clientMessage(cause, "Could not update that table");
        return NextResponse.json({ error: message }, { status: 400 });
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

// DELETE /api/grid/tables/[tableId] — columns, rows, jobs and runs cascade.
export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(_req, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId)) return NextResponse.json({ error: "not found" }, { status: 404 });
      let ok: boolean;
      try {
        ok = await deleteTable(tableId);
      } catch (error) {
        if (error instanceof LastTableError) {
          return NextResponse.json({ error: error.message }, { status: 409 });
        }
        throw error;
      }
      if (!ok) return NextResponse.json({ error: "not found" }, { status: 404 });
      return NextResponse.json({ ok: true });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
