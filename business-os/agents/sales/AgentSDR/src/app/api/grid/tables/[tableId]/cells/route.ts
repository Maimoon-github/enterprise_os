import { NextRequest, NextResponse } from "next/server";
import { listRowsByIds, setCellValue, setCellValues, type CellValueUpdate } from "@/lib/grid/rows";
import { cascadeRows } from "@/lib/grid/queue";
import { changedCellUpdates } from "@/lib/grid/cascade-targets";
import { listColumns } from "@/lib/grid/columns";
import { isStaticColumnType } from "@/lib/grid/types";
import { coerceCellInput } from "@/lib/grid/cell-input";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Queues the dependents of the cells that just changed, in one batch. The edit
 * is already saved, so a failure here is logged and reported as nothing queued
 * rather than failing the request.
 */
async function queueDependents(
  tableId: string,
  columns: Awaited<ReturnType<typeof listColumns>>,
  changed: CellValueUpdate[],
  knownCells?: Map<string, Record<string, unknown>>,
): Promise<number> {
  if (!changed.length) return 0;
  try {
    const keysByRow = new Map<string, string[]>();
    for (const { rowId, columnKey } of changed) keysByRow.set(rowId, [...(keysByRow.get(rowId) ?? []), columnKey]);

    const cellsByRow = knownCells ?? new Map<string, Record<string, unknown>>();
    const missing = [...keysByRow.keys()].filter((id) => !cellsByRow.has(id));
    if (missing.length) {
      for (const row of await listRowsByIds(tableId, missing)) cellsByRow.set(row.id, row.cells ?? {});
    }

    return await cascadeRows(
      tableId,
      [...keysByRow].flatMap(([rowId, changedKeys]) => {
        const cells = cellsByRow.get(rowId);
        return cells ? [{ rowId, cells, changedKeys }] : [];
      }),
      columns,
    );
  } catch (err) {
    console.error("[grid/cells] could not queue dependents:", err);
    return 0;
  }
}

// PATCH /api/grid/tables/[tableId]/cells — { rowId, columnKey, value }
//
// Editing is only allowed on static columns. A runner column's value is
// owned by the worker, and letting the UI write it would be silently undone
// by the next run — confusing rather than useful.
//
// An edit that changes a value queues the columns that read it (subject to the
// table's and each column's Auto-run); `queued` says how many, so the client
// knows to start polling.
export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(req, async () => {
      const { tableId } = await params;

      let body: {
        rowId?: string;
        columnKey?: string;
        value?: unknown;
        updates?: CellValueUpdate[];
      };
      try {
        body = await req.json();
      } catch {
        return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
      }
      if (!body || typeof body !== "object" || Array.isArray(body)) {
        return NextResponse.json({ error: "body must be an object" }, { status: 400 });
      }

      const columns = await listColumns(tableId);
      const columnsByKey = new Map(columns.map((column) => [column.key, column]));

      if (body.updates !== undefined) {
        if (!Array.isArray(body.updates) || body.updates.length === 0 || body.updates.length > 50_000) {
          return NextResponse.json(
            { error: "updates must contain between 1 and 50,000 cells" },
            { status: 400 },
          );
        }
        const cells = new Set<string>();
        const rowIds = new Set<string>();
        const coerced: CellValueUpdate[] = [];
        for (const update of body.updates) {
          if (!update || typeof update.rowId !== "string" || typeof update.columnKey !== "string") {
            return NextResponse.json({ error: "every update needs a rowId and columnKey" }, { status: 400 });
          }
          rowIds.add(update.rowId);
          if (rowIds.size > 1_000) {
            return NextResponse.json({ error: "updates cannot span more than 1,000 rows" }, { status: 400 });
          }
          if (!UUID.test(update.rowId)) {
            return NextResponse.json({ error: "every update needs a valid rowId" }, { status: 400 });
          }
          const cell = `${update.rowId}\u0000${update.columnKey}`;
          if (cells.has(cell)) {
            return NextResponse.json({ error: "updates cannot contain the same cell twice" }, { status: 400 });
          }
          cells.add(cell);
          const column = columnsByKey.get(update.columnKey);
          if (!column) {
            return NextResponse.json({ error: `unknown column "${update.columnKey}"` }, { status: 400 });
          }
          if (!isStaticColumnType(column.type)) {
            return NextResponse.json(
              { error: `"${column.name}" is a ${column.type} column — its value is set by running it` },
              { status: 400 },
            );
          }
          const input = coerceCellInput(update.value, column.type);
          if (!input.ok) {
            return NextResponse.json({ error: `"${column.name}": ${input.error}` }, { status: 400 });
          }
          coerced.push({ rowId: update.rowId, columnKey: update.columnKey, value: input.value });
        }

        try {
          const result = await setCellValues(tableId, coerced);
          const queued = await queueDependents(
            tableId,
            columns,
            changedCellUpdates(result.previousValues, coerced),
          );
          return NextResponse.json({ updatedCells: body.updates.length, ...result, queued });
        } catch (cause) {
          return NextResponse.json(
            { error: cause instanceof Error ? cause.message : "could not update cells" },
            { status: 400 },
          );
        }
      }

      if (!body.rowId || !body.columnKey) {
        return NextResponse.json({ error: "rowId and columnKey are required" }, { status: 400 });
      }
      if (!UUID.test(body.rowId)) {
        return NextResponse.json({ error: "rowId must be a valid UUID" }, { status: 400 });
      }

      const column = columnsByKey.get(body.columnKey);
      if (!column) return NextResponse.json({ error: "unknown column" }, { status: 400 });
      if (!isStaticColumnType(column.type)) {
        return NextResponse.json(
          { error: `"${column.name}" is a ${column.type} column — its value is set by running it` },
          { status: 400 },
        );
      }

      const input = coerceCellInput(body.value, column.type);
      if (!input.ok) return NextResponse.json({ error: `"${column.name}": ${input.error}` }, { status: 400 });

      const [before] = await listRowsByIds(tableId, [body.rowId]);
      const row = await setCellValue(tableId, body.rowId, body.columnKey, input.value);
      if (!row) return NextResponse.json({ error: "row not found" }, { status: 404 });

      const queued = await queueDependents(
        tableId,
        columns,
        changedCellUpdates(
          [{ rowId: body.rowId, columnKey: body.columnKey, value: before?.cells?.[body.columnKey] ?? null }],
          [{ rowId: body.rowId, columnKey: body.columnKey, value: input.value }],
        ),
        new Map([[row.id, row.cells ?? {}]]),
      );

      return NextResponse.json({ row, queued });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
