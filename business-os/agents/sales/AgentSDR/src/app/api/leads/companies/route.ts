import { NextRequest, NextResponse } from "next/server";
import { listCompanies, upsertCompany, withLeadTransaction } from "@/lib/leads/records";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";

export async function GET(req: NextRequest) {
  try {
    return await withOrgContext(req, () => list(req));
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}

async function list(req: NextRequest) {
  const sort = req.nextUrl.searchParams.get("sort");
  const direction = req.nextUrl.searchParams.get("direction");
  const result = await listCompanies({
    q: req.nextUrl.searchParams.get("q") ?? undefined,
    limit: Number(req.nextUrl.searchParams.get("limit") ?? 50),
    offset: Number(req.nextUrl.searchParams.get("offset") ?? 0),
    sort: sort === "name" || sort === "domain" || sort === "people" || sort === "updated" ? sort : undefined,
    direction: direction === "asc" || direction === "desc" ? direction : undefined,
  });
  return NextResponse.json({ companies: result.rows, total: result.total });
}

export async function POST(req: NextRequest) {
  try {
    return await withOrgContext(req, () => create(req));
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}

async function create(req: NextRequest) {
  const body = await req.json().catch(() => null);
  if (!body || typeof body.domain !== "string") return NextResponse.json({ error: "domain is required" }, { status: 400 });
  try {
    const company = await withLeadTransaction((tx) =>
      upsertCompany(tx, {
        domain: body.domain,
        name: typeof body.name === "string" ? body.name : null,
        linkedinUrl: typeof body.linkedinUrl === "string" ? body.linkedinUrl : null,
        source: "manual",
      }),
    );
    if (!company) return NextResponse.json({ error: "domain is required" }, { status: 400 });
    return NextResponse.json({ company }, { status: 201 });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Could not save company" }, { status: 400 });
  }
}
