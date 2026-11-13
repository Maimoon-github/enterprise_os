import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { startSearchBatchRun } from "@/lib/linkedin/searchBatches";

const isStringArray = (v: unknown): v is string[] => Array.isArray(v) && v.every((s) => typeof s === "string");

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(req, async () => {
    const { id } = await params;

    try {
      const raw = await req.text();
      const body: unknown = raw ? JSON.parse(raw) : {};
      const obj = (typeof body === "object" && body !== null ? body : {}) as Record<string, unknown>;
      const accountIds = "accountIds" in obj ? obj.accountIds : undefined;
      if (accountIds !== undefined && !isStringArray(accountIds)) {
        return NextResponse.json({ ok: false, error: "accountIds must be an array of strings" }, { status: 400 });
      }
      // Absent means every runnable URL in the batch; a list runs only those.
      const queryIds = "queryIds" in obj ? obj.queryIds : undefined;
      if (queryIds !== undefined && !isStringArray(queryIds)) {
        return NextResponse.json({ ok: false, error: "queryIds must be an array of strings" }, { status: 400 });
      }

      const result = await startSearchBatchRun(id, accountIds, queryIds);
      return NextResponse.json({ ok: true, ...result });
    } catch (err) {
      if (err instanceof Error && err.message === "Search not found") {
        return NextResponse.json({ ok: false, error: err.message }, { status: 404 });
      }
      if (err instanceof Error && err.message === "Unknown account") {
        return NextResponse.json({ ok: false, error: err.message }, { status: 400 });
      }
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
