import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { desc } from "drizzle-orm";
import { db } from "@/lib/db";
import { leads } from "@/lib/linkedin/schema";
import { buildLeadWhere } from "@/lib/linkedin/leadListFilters";

export async function GET(req: NextRequest) {
  return withLinkedinOrg(req, async () => {
    const { searchParams } = new URL(req.url);
    const status = searchParams.get("status") ?? undefined;
    const search = searchParams.get("search") ?? undefined;
    const accountId = searchParams.get("accountId") ?? undefined;
    const campaignId = searchParams.get("campaignId") ?? undefined;

    try {
      const where = buildLeadWhere({ status, search, accountId, campaignId });
      const rows = await db
        .select({ id: leads.id })
        .from(leads)
        .where(where)
        .orderBy(desc(leads.updatedAt));

      return NextResponse.json({
        ok: true,
        ids: rows.map((l) => l.id),
        total: rows.length,
      });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
