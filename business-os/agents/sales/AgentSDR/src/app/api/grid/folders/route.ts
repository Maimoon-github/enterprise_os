import { NextRequest, NextResponse } from "next/server";
import { createFolder, listFolders, listAllFolders } from "@/lib/grid/folders";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { isRecord, isUuid, nullableUuid, optionalName } from "@/lib/grid/validate";
import { FolderNotFoundError } from "@/lib/grid/folders";

// GET /api/grid/folders?parent=<id>       — direct children of one folder
// GET /api/grid/folders?parent=root       — folders at the root
// GET /api/grid/folders                   — every folder, flat (move pickers)
export async function GET(req: NextRequest) {
  try {
    return await withOrgContext(req, async () => {
      const parent = req.nextUrl.searchParams.get("parent");
      if (parent === null) return NextResponse.json({ folders: await listAllFolders() });
      if (parent !== "root" && !isUuid(parent)) {
        return NextResponse.json({ error: "parent is not a valid id" }, { status: 400 });
      }

      const folders = await listFolders(parent === "root" ? null : parent);
      return NextResponse.json({ folders });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

// POST /api/grid/folders — { name?, parentId? }
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

      const name = optionalName(body.name, "name", true);
      if (!name.ok) return NextResponse.json({ error: name.error }, { status: 400 });
      const parent = nullableUuid(body.parentId, "parentId");
      if (!parent.ok) return NextResponse.json({ error: parent.error }, { status: 400 });

      try {
        const folder = await createFolder({
          name: name.value ?? "Untitled folder",
          parentId: parent.value ?? null,
        });
        return NextResponse.json({ folder }, { status: 201 });
      } catch (cause) {
        // Another organization's folder reads exactly like a deleted one.
        if (cause instanceof FolderNotFoundError) {
          return NextResponse.json({ error: "parent folder not found" }, { status: 404 });
        }
        throw cause;
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
