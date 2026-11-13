import { NextRequest, NextResponse } from "next/server";
import { deleteAiConnection } from "@/lib/ai/connections";
import { authContextErrorResponse, requirePermission, withOrgContext } from "@/lib/auth/context";
import { isUuid } from "@/lib/grid/validate";

// DELETE /api/grid/ai/connections/[connectionId]
export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ connectionId: string }> },
) {
  try {
    return await withOrgContext(_req, async (ctx) => {
      requirePermission(ctx, { integrations: ["manage"] });
      const { connectionId } = await params;
      if (!isUuid(connectionId)) return NextResponse.json({ error: "not found" }, { status: 404 });
      const ok = await deleteAiConnection(connectionId);
      if (!ok) return NextResponse.json({ error: "not found" }, { status: 404 });
      return NextResponse.json({ ok: true });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
