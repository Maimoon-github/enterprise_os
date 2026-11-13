import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { resetSearchQueries, searchBatchExists, startSearchBatchRun } from "@/lib/linkedin/searchBatches";

const isStringArray = (v: unknown): v is string[] => Array.isArray(v) && v.every((s) => typeof s === "string" && s);

/**
 * Re-runs specific search URLs: their existing leads are deleted, the rows go back to
 * QUEUED, and a run is started for just those URLs. A URL that is mid-run is left as it
 * is and reported in `skipped`.
 */
export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(req, async () => {
    const { id } = await params;

    try {
      const body: unknown = await req.json();
      const obj = (typeof body === "object" && body !== null ? body : {}) as Record<string, unknown>;
      const ids = obj.ids;
      if (!isStringArray(ids) || ids.length === 0) {
        return NextResponse.json({ ok: false, error: "ids must be a non-empty array of query ids" }, { status: 400 });
      }
      const accountIds = obj.accountIds;
      if (accountIds !== undefined && !isStringArray(accountIds)) {
        return NextResponse.json({ ok: false, error: "accountIds must be an array of strings" }, { status: 400 });
      }

      if (!(await searchBatchExists(id))) {
        return NextResponse.json({ ok: false, error: "Search not found" }, { status: 404 });
      }

      const reset = await resetSearchQueries(id, ids);
      if (reset.reset === 0) {
        return NextResponse.json({ ok: true, ...reset, started: false, reason: "nothing_to_rerun" });
      }

      const run = await startSearchBatchRun(id, accountIds, ids);
      return NextResponse.json({ ok: true, ...reset, ...run });
    } catch (err) {
      if (err instanceof Error && err.message === "Unknown account") {
        return NextResponse.json({ ok: false, error: err.message }, { status: 400 });
      }
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
