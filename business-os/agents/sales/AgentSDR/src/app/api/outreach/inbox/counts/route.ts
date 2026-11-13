import { NextRequest, NextResponse } from "next/server";
import { getInboxSidebarCounts } from "@/lib/inbox/queries";
import { withOrgContext, authContextErrorResponse } from "@/lib/auth/context";

// GET /api/outreach/inbox/counts
export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => {
      const counts = await getInboxSidebarCounts();
      return NextResponse.json(counts);
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
