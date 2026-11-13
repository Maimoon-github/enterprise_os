import { NextRequest, NextResponse } from "next/server";
import { markMessageOpened } from "@/lib/inbox/queries";
import { withOrgContext, authContextErrorResponse } from "@/lib/auth/context";

// POST /api/outreach/inbox/messages/[id]/opened
export async function POST(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withOrgContext(_req, async () => {
      const { id } = await params;
      await markMessageOpened(id);
      return NextResponse.json({ ok: true });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
