import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, eq, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { searchBatches, searchQueries } from "@/lib/linkedin/schema";
import { inOrg } from "@/lib/tenancy/scope";

// SearchQuery belongs to the organization of its SearchBatch.
const ownQuery = (id: string) =>
  and(
    eq(searchQueries.id, id),
    inArray(searchQueries.batchId, db.select({ id: searchBatches.id }).from(searchBatches).where(inOrg(searchBatches))),
  );

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(_req, async () => {
    const { id } = await params;

    try {
      const [query] = await db
        .select({ status: searchQueries.status })
        .from(searchQueries)
        .where(ownQuery(id))
        .limit(1);
      if (!query) {
        return NextResponse.json({ ok: false, error: "Search not found" }, { status: 404 });
      }

      if (query.status === "RUNNING") {
        // Let the in-flight job loop notice and stop on its own next page check.
        await db.update(searchQueries).set({ status: "CANCELLED" }).where(ownQuery(id));
      } else {
        await db.delete(searchQueries).where(ownQuery(id));
      }

      return NextResponse.json({ ok: true });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
