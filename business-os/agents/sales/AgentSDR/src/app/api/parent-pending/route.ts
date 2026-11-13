import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { listParentPending } from "@/lib/qualification";

// GET /api/parent-pending — review list of domains awaiting manual parent research.
export async function GET(req: NextRequest) {
  try {
    return await withOrgContext(req, async () => {
      const rows = await listParentPending();
      return NextResponse.json({ count: rows.length, domains: rows });
    });
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}
