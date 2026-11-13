import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { qualifyDomain } from "@/lib/qualification";

// Single-domain debug endpoint. Runs the pipeline and returns the result row.
// e.g. GET /api/qualify?domain=apollo.io&force=1
export async function GET(req: NextRequest) {
  try {
    return await withOrgContext(req, () => qualify(req));
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}

async function qualify(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const domain = searchParams.get("domain");
  if (!domain) {
    return NextResponse.json({ error: "domain is required" }, { status: 400 });
  }
  const force = searchParams.get("force") === "1";

  try {
    const result = await qualifyDomain(domain.trim().toLowerCase(), { force });
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "qualification failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
