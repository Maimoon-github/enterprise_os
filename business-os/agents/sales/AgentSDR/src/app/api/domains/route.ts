import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse, requireOrgContext } from "@/lib/auth/context";
import { getDomains } from "@/lib/queries";

export async function GET(req: NextRequest) {
  // The domains dataset is global: no organization scope is opened, but the
  // caller must still be a member of an organization.
  try {
    await requireOrgContext(req);
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
  const { searchParams } = req.nextUrl;

  const result = await getDomains({
    page: searchParams.get("page") ?? undefined,
    pageSize: searchParams.get("pageSize") ?? undefined,
    countryCode: searchParams.get("countryCode") ?? undefined,
    c1: searchParams.get("c1") ?? undefined,
    c2: searchParams.get("c2") ?? undefined,
    c3: searchParams.get("c3") ?? undefined,
    platform: searchParams.get("platform") ?? undefined,
    minRevenue: searchParams.get("minRevenue") ?? undefined,
    maxRevenue: searchParams.get("maxRevenue") ?? undefined,
    sortBy: searchParams.get("sortBy") ?? undefined,
    sortDir: searchParams.get("sortDir") ?? undefined,
  });

  return NextResponse.json(result);
}
