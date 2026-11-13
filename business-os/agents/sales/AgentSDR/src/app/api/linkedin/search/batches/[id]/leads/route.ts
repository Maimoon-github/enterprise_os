import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { deleteSearchLeads, searchBatchExists } from "@/lib/linkedin/searchBatches";

/**
 * Bulk-remove leads from this batch. Keyed by `linkedinUrl` (the identifier the Leads
 * tab de-duplicates on) rather than row id, so a lead found by several of the batch's
 * URLs goes away entirely instead of reappearing from another one.
 */
export async function DELETE(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(req, async () => {
    const { id } = await params;

    try {
      const body: unknown = await req.json();
      const urls =
        typeof body === "object" && body !== null && "linkedinUrls" in body
          ? (body as { linkedinUrls: unknown }).linkedinUrls
          : undefined;
      if (!Array.isArray(urls) || urls.length === 0 || !urls.every((v) => typeof v === "string" && v)) {
        return NextResponse.json(
          { ok: false, error: "linkedinUrls must be a non-empty array of identifiers" },
          { status: 400 }
        );
      }

      if (!(await searchBatchExists(id))) {
        return NextResponse.json({ ok: false, error: "Search not found" }, { status: 404 });
      }

      const deleted = await deleteSearchLeads(id, urls);
      return NextResponse.json({ ok: true, deleted });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
