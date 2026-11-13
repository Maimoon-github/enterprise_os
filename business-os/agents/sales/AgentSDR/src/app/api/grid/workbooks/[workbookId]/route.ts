import { NextRequest, NextResponse } from "next/server";
import {
  deleteWorkbook,
  getWorkbook,
  listWorkbookTables,
  updateWorkbook,
} from "@/lib/grid/workbooks";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { clientMessage, isRecord, isUuid, nullableUuid, optionalName } from "@/lib/grid/validate";

// GET /api/grid/workbooks/[workbookId] — workbook plus its sheet tabs.
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ workbookId: string }> },
) {
  try {
    return await withOrgContext(_req, async () => {
      const { workbookId } = await params;
      if (!isUuid(workbookId)) return NextResponse.json({ error: "not found" }, { status: 404 });
      const workbook = await getWorkbook(workbookId);
      if (!workbook) return NextResponse.json({ error: "not found" }, { status: 404 });

      const tables = await listWorkbookTables(workbookId);
      return NextResponse.json({ workbook, tables });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

// PATCH /api/grid/workbooks/[workbookId] — { name?, description?, folderId? }
export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ workbookId: string }> },
) {
  try {
    return await withOrgContext(req, async () => {
      const { workbookId } = await params;
      if (!isUuid(workbookId)) return NextResponse.json({ error: "not found" }, { status: 404 });

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
      const folder = nullableUuid(body.folderId, "folderId");
      if (!folder.ok) return badRequest(folder.error);
      if (body.description !== undefined && body.description !== null && typeof body.description !== "string") {
        return badRequest("description must be text");
      }

      try {
        const workbook = await updateWorkbook(workbookId, {
          name: name.value,
          description: body.description as string | null | undefined,
          folderId: folder.value,
        });
        if (!workbook) return NextResponse.json({ error: "not found" }, { status: 404 });
        return NextResponse.json({ workbook });
      } catch (cause) {
        // A move to a folder that has since been deleted — the caller's stale
        // view, not a server fault.
        const message = clientMessage(cause, "Could not update that workbook");
        return NextResponse.json({ error: message }, { status: 400 });
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

// DELETE /api/grid/workbooks/[workbookId] — cascades to every sheet.
export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ workbookId: string }> },
) {
  try {
    return await withOrgContext(_req, async () => {
      const { workbookId } = await params;
      if (!isUuid(workbookId)) return NextResponse.json({ error: "not found" }, { status: 404 });
      const ok = await deleteWorkbook(workbookId);
      if (!ok) return NextResponse.json({ error: "not found" }, { status: 404 });
      return NextResponse.json({ ok: true });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
