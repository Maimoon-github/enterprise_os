import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, asc, eq, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { searchBatches, searchQueries, searchResults } from "@/lib/linkedin/schema";

export async function GET(req: NextRequest) {
  return withLinkedinOrg(req, async () => {
    const idsParam = req.nextUrl.searchParams.get("ids");
    if (!idsParam) {
      return NextResponse.json({ ok: false, error: "Missing ids" }, { status: 400 });
    }

    const ids = idsParam.split(",").map((s) => s.trim()).filter(Boolean);
    if (ids.length === 0) {
      return NextResponse.json({ ok: false, error: "Missing ids" }, { status: 400 });
    }

    const rows = await db
      .select({
        result: searchResults,
        companyName: searchQueries.companyName,
      })
      .from(searchResults)
      .innerJoin(searchQueries, eq(searchResults.searchQueryId, searchQueries.id))
      .where(and(
        inArray(searchResults.searchQueryId, ids),
        inArray(searchQueries.batchId, db.select({ id: searchBatches.id }).from(searchBatches).where(inOrg(searchBatches))),
      ))
      .orderBy(asc(searchResults.createdAt));

    const flattened = rows.map(({ result, companyName }) => ({
      ...result,
      companyName,
    }));

    // Dedupe across the selected searches — the same person can surface from more than one URL.
    const byUrl = new Map<string, (typeof flattened)[number]>();
    for (const row of flattened) {
      if (!byUrl.has(row.linkedinUrl)) byUrl.set(row.linkedinUrl, row);
    }

    return NextResponse.json({ ok: true, results: [...byUrl.values()] });
  });
}
