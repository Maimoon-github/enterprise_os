import { NextRequest, NextResponse } from "next/server";
import { deleteColumn, updateColumn } from "@/lib/grid/columns";
import { ALL_COLUMN_TYPES, type ColumnConfig, type ColumnType } from "@/lib/grid/types";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { clientMessage, isRecord, isUuid, optionalName } from "@/lib/grid/validate";

// PATCH /api/grid/tables/[tableId]/columns/[columnId]
//   { name?, type?, config?, autoRun?, afterColumnId? }
// Every field present is applied in one save — a body with `afterColumnId`
// and a new name moves AND renames. `afterColumnId` is another column of this
// table, or null for "move to the front". A name another column already uses
// is a 400. Renaming only touches this row — grid_rows.cells is keyed by the
// immutable `key`, never by `name`.
export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ tableId: string; columnId: string }> },
) {
  try {
    return await withOrgContext(req, async () => {
      const { tableId, columnId } = await params;
      if (!isUuid(tableId) || !isUuid(columnId)) {
        return NextResponse.json({ error: "not found" }, { status: 404 });
      }

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
      if (body.type !== undefined && (typeof body.type !== "string" || !ALL_COLUMN_TYPES.includes(body.type as ColumnType))) {
        return badRequest(`type must be one of: ${ALL_COLUMN_TYPES.join(", ")}`);
      }
      if (body.config !== undefined && !isRecord(body.config)) return badRequest("config must be an object");
      if (body.autoRun !== undefined && typeof body.autoRun !== "boolean") {
        return badRequest("autoRun must be true or false");
      }
      if (body.afterColumnId !== undefined && body.afterColumnId !== null && !isUuid(body.afterColumnId)) {
        return badRequest("afterColumnId is not a valid id");
      }

      try {
        const column = await updateColumn(
          columnId,
          {
            name: name.value,
            type: body.type as ColumnType | undefined,
            config: body.config as ColumnConfig | undefined,
            autoRun: body.autoRun as boolean | undefined,
            afterColumnId: body.afterColumnId as string | null | undefined,
          },
          tableId,
        );
        if (!column) return NextResponse.json({ error: "not found" }, { status: 404 });
        return NextResponse.json({ column });
      } catch (err) {
        return badRequest(clientMessage(err, "could not update column"));
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

// DELETE /api/grid/tables/[tableId]/columns/[columnId][?withOutputs=1]
// Also strips the key from every row's JSONB and drops the column's queued
// jobs — see deleteColumn(). `withOutputs=1` on an AI / enrichment column
// deletes the output columns it writes into as well; without it, a source that
// still has outputs is refused ("Column is used by: …"). Anything ELSE that
// depends on the column keeps blocking the delete either way.
// Responds { ok: true, deletedColumnIds: string[] }.
export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ tableId: string; columnId: string }> },
) {
  try {
    return await withOrgContext(_req, async () => {
      const { tableId, columnId } = await params;
      if (!isUuid(tableId) || !isUuid(columnId)) {
        return NextResponse.json({ error: "not found" }, { status: 404 });
      }
      const flag = _req.nextUrl.searchParams.get("withOutputs");
      const withOutputs = flag === "1" || flag === "true";
      try {
        const result = await deleteColumn(columnId, { withOutputs, tableId });
        if (!result) return NextResponse.json({ error: "not found" }, { status: 404 });
        return NextResponse.json({ ok: true, deletedColumnIds: result.deletedIds });
      } catch (err) {
        return NextResponse.json({ error: clientMessage(err, "could not delete column") }, { status: 400 });
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
