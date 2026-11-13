import { NextRequest, NextResponse } from "next/server";
import { createColumn, listColumns } from "@/lib/grid/columns";
import { getTable } from "@/lib/grid/tables";
import { ALL_COLUMN_TYPES, type ColumnConfig, type ColumnType } from "@/lib/grid/types";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { clientMessage, isRecord, isUuid, requireString } from "@/lib/grid/validate";

// GET /api/grid/tables/[tableId]/columns
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(_req, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId) || !(await getTable(tableId))) {
        return NextResponse.json({ error: "table not found" }, { status: 404 });
      }
      const columns = await listColumns(tableId);
      return NextResponse.json({ columns });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

// POST /api/grid/tables/[tableId]/columns
//   { name, type, config?, autoRun?, afterColumnId?, beforeColumnId?, copyValuesFrom? }
//
// A name another column already uses (case-insensitive) is suffixed — "Text"
// becomes "Text 2" — and the column that comes back carries the final name.
// `copyValuesFrom` is the KEY of a data column whose cell values are copied
// into the new column (duplicate column); the new type must be a data type.
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(req, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId) || !(await getTable(tableId))) {
        return NextResponse.json({ error: "table not found" }, { status: 404 });
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
      const name = requireString(body.name, "name");
      if (!name.ok) return badRequest(name.error);
      if (typeof body.type !== "string" || !ALL_COLUMN_TYPES.includes(body.type as ColumnType)) {
        return badRequest(`type must be one of: ${ALL_COLUMN_TYPES.join(", ")}`);
      }
      if (body.config !== undefined && body.config !== null && !isRecord(body.config)) {
        return badRequest("config must be an object");
      }
      if (body.autoRun !== undefined && typeof body.autoRun !== "boolean") {
        return badRequest("autoRun must be true or false");
      }
      for (const field of ["afterColumnId", "beforeColumnId"] as const) {
        if (body[field] !== undefined && !isUuid(body[field])) return badRequest(`${field} is not a valid id`);
      }
      if (body.copyValuesFrom !== undefined && (typeof body.copyValuesFrom !== "string" || !body.copyValuesFrom)) {
        return badRequest("copyValuesFrom must be a column key");
      }

      try {
        const column = await createColumn({
          tableId,
          name: name.value,
          type: body.type as ColumnType,
          config: (body.config ?? undefined) as ColumnConfig | undefined,
          autoRun: body.autoRun as boolean | undefined,
          afterColumnId: body.afterColumnId as string | undefined,
          beforeColumnId: body.beforeColumnId as string | undefined,
          copyValuesFrom: body.copyValuesFrom as string | undefined,
        });
        return NextResponse.json({ column }, { status: 201 });
      } catch (err) {
        // assertNoCycle throws here — a 400 rather than a 500, since it's the
        // user's column config that's wrong, not the server.
        return badRequest(clientMessage(err, "could not create column"));
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
