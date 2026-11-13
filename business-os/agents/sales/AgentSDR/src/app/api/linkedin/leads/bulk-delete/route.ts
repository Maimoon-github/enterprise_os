import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { leads } from "@/lib/linkedin/schema";
import { buildLeadWhere, type LeadListFilters } from "@/lib/linkedin/leadListFilters";

const parseFilters = (raw: unknown): LeadListFilters => {
  if (!raw || typeof raw !== "object") return {};
  const f = raw as Record<string, unknown>;
  return {
    status: typeof f.status === "string" && f.status ? f.status : undefined,
    search: typeof f.search === "string" ? f.search : undefined,
    accountId: typeof f.accountId === "string" && f.accountId ? f.accountId : undefined,
    campaignId: typeof f.campaignId === "string" && f.campaignId ? f.campaignId : undefined,
  };
};

export async function POST(req: NextRequest) {
  return withLinkedinOrg(req, async () => {
    try {
      const body = await req.json();

      if (body?.matchFilters === true) {
        const filters = parseFilters(body.filters);
        const deletedRows = await db.transaction(async (tx) => {
          const rows = await tx.select({ id: leads.id }).from(leads).where(buildLeadWhere(filters));
          if (!rows.length) return [];
          const rowIds = rows.map((row) => row.id);
          return tx.delete(leads).where(and(inOrg(leads), inArray(leads.id, rowIds))).returning({ id: leads.id });
        });
        return NextResponse.json({ ok: true, deleted: deletedRows.length });
      }

      const ids = body?.ids;
      if (!Array.isArray(ids) || ids.length === 0) {
        return NextResponse.json(
          { ok: false, error: "ids array or matchFilters required" },
          { status: 400 }
        );
      }

      const validIds = ids.filter((id: unknown): id is string => typeof id === "string" && id.length > 0);
      if (validIds.length === 0) {
        return NextResponse.json({ ok: false, error: "No valid ids" }, { status: 400 });
      }

      const deletedRows = await db.transaction(async (tx) => {
        return tx.delete(leads).where(and(inOrg(leads), inArray(leads.id, validIds))).returning({ id: leads.id });
      });

      return NextResponse.json({ ok: true, deleted: deletedRows.length });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
