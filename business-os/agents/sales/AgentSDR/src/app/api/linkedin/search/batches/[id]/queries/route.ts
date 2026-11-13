import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { addSearchUrls, deleteSearchQueries, searchBatchExists, type SearchUrlInput } from "@/lib/linkedin/searchBatches";

const isUrlRows = (v: unknown): v is { url: string; companyName?: string | null }[] =>
  Array.isArray(v) &&
  v.length > 0 &&
  v.every(
    (r) =>
      typeof r === "object" &&
      r !== null &&
      typeof (r as { url: unknown }).url === "string" &&
      ((r as { companyName?: unknown }).companyName === undefined ||
        (r as { companyName?: unknown }).companyName === null ||
        typeof (r as { companyName?: unknown }).companyName === "string")
  );

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(req, async () => {
    const { id } = await params;

    try {
      const body: unknown = await req.json();
      if (typeof body !== "object" || body === null) {
        return NextResponse.json({ ok: false, error: "Invalid request body" }, { status: 400 });
      }
      const { urls } = body as Record<string, unknown>;
      if (!isUrlRows(urls)) {
        return NextResponse.json({ ok: false, error: "urls must be a non-empty array of { url, companyName? }" }, { status: 400 });
      }

      if (!(await searchBatchExists(id))) {
        return NextResponse.json({ ok: false, error: "Search not found" }, { status: 404 });
      }

      const rows: SearchUrlInput[] = urls.map((u) => ({ url: u.url, companyName: u.companyName ?? null }));
      const added = await addSearchUrls(id, rows);

      return NextResponse.json({ ok: true, added });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}

/** Bulk-remove search URLs (and the leads they found) from this batch. */
export async function DELETE(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(req, async () => {
    const { id } = await params;

    try {
      const body: unknown = await req.json();
      const ids =
        typeof body === "object" && body !== null && "ids" in body ? (body as { ids: unknown }).ids : undefined;
      if (!Array.isArray(ids) || ids.length === 0 || !ids.every((v) => typeof v === "string" && v)) {
        return NextResponse.json({ ok: false, error: "ids must be a non-empty array of query ids" }, { status: 400 });
      }

      if (!(await searchBatchExists(id))) {
        return NextResponse.json({ ok: false, error: "Search not found" }, { status: 404 });
      }

      const result = await deleteSearchQueries(id, ids);
      return NextResponse.json({ ok: true, ...result });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
