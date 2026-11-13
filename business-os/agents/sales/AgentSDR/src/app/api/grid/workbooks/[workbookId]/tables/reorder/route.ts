import { NextRequest, NextResponse } from "next/server";
import { reorderTables } from "@/lib/grid/tables";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { clientMessage, isRecord, isUuid } from "@/lib/grid/validate";

// POST /api/grid/workbooks/[workbookId]/tables/reorder — { tableIds: [...] }
//
// Scoped under the workbook rather than sitting at /api/grid/tables/reorder,
// where a static segment would shadow the [tableId] route.
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ workbookId: string }> },
) {
  try {
    return await withOrgContext(req, async () => {
      const { workbookId } = await params;
      if (!isUuid(workbookId)) return NextResponse.json({ error: "not found" }, { status: 404 });

      let body: { tableIds?: unknown };
      try {
        const parsed = await req.json();
        if (!isRecord(parsed)) throw new Error("not an object");
        body = parsed;
      } catch {
        return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
      }

      if (!Array.isArray(body.tableIds)) {
        return NextResponse.json({ error: "tableIds must be an array" }, { status: 400 });
      }
      if (!body.tableIds.every(isUuid)) {
        return NextResponse.json({ error: "tableIds must be valid table ids" }, { status: 400 });
      }

      try {
        const tables = await reorderTables(workbookId, body.tableIds);
        return NextResponse.json({ tables });
      } catch (cause) {
        const message = clientMessage(cause, "Could not reorder those tables");
        return NextResponse.json({ error: message }, { status: 400 });
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
