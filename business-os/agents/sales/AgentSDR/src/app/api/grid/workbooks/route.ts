import { NextRequest, NextResponse } from "next/server";
import { createWorkbook, listWorkbooks } from "@/lib/grid/workbooks";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { isRecord, isUuid, nullableUuid, optionalName } from "@/lib/grid/validate";

// GET /api/grid/workbooks             — every workbook
// GET /api/grid/workbooks?folder=<id>  — workbooks filed in one folder
// GET /api/grid/workbooks?folder=root  — workbooks at the root
export async function GET(req: NextRequest) {
  try {
    return await withOrgContext(req, async () => {
      const folder = req.nextUrl.searchParams.get("folder");
      if (folder !== null && folder !== "root" && !isUuid(folder)) {
        return NextResponse.json({ error: "folder is not a valid id" }, { status: 400 });
      }
      const workbooks = await listWorkbooks(
        folder === null ? "all" : folder === "root" ? null : folder,
      );
      return NextResponse.json({ workbooks });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

// POST /api/grid/workbooks — { name?, firstTableName?, folderId? }
export async function POST(req: NextRequest) {
  try {
    return await withOrgContext(req, async () => {
      let body: Record<string, unknown>;
      try {
        const parsed = await req.json();
        body = isRecord(parsed) ? parsed : {};
      } catch {
        body = {};
      }

      const badRequest = (error: string) => NextResponse.json({ error }, { status: 400 });
      const name = optionalName(body.name, "name", true);
      if (!name.ok) return badRequest(name.error);
      const firstTableName = optionalName(body.firstTableName, "firstTableName", true);
      if (!firstTableName.ok) return badRequest(firstTableName.error);
      const folder = nullableUuid(body.folderId, "folderId");
      if (!folder.ok) return badRequest(folder.error);

      const created = await createWorkbook({
        name: name.value ?? "Untitled workbook",
        firstTableName: firstTableName.value,
        folderId: folder.value ?? null,
      });
      return NextResponse.json(created, { status: 201 });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
