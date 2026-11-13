import { NextRequest, NextResponse } from "next/server";
import { suggestCompanies } from "@/lib/leads/records";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";

/** GET /api/leads/companies/suggest?q= — the company-name type-ahead. */
export async function GET(req: NextRequest) {
  try {
    return await withOrgContext(req, async () => {
      const q = (req.nextUrl.searchParams.get("q") ?? "").slice(0, 120);
      return NextResponse.json({ companies: await suggestCompanies(q) });
    });
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}
