import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { deleteSearchBatch, searchBatchExists, getSearchBatchDetail, isSearchJobRunning } from "@/lib/linkedin/searchBatches";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(_req, async () => {
    const { id } = await params;

    try {
      const detail = await getSearchBatchDetail(id);
      if (!detail) {
        return NextResponse.json({ ok: false, error: "Search not found" }, { status: 404 });
      }
      const jobRunning = await isSearchJobRunning();
      return NextResponse.json({ ok: true, detail, jobRunning });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(_req, async () => {
    const { id } = await params;

    try {
      if (!(await searchBatchExists(id))) {
        return NextResponse.json({ ok: false, error: "Search not found" }, { status: 404 });
      }

      const result = await deleteSearchBatch(id);
      if (!result.ok) {
        return NextResponse.json({ ok: false, error: result.reason }, { status: 409 });
      }
      return NextResponse.json({ ok: true });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
