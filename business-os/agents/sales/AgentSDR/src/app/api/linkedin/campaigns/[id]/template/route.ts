import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { campaigns } from "@/lib/linkedin/schema";
import { buildLeadsTemplateBuffer, campaignLeadTemplateFilename } from "@/lib/linkedin/leadsTemplate";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(_req, async () => {
    const { id } = await params;

    const [campaign] = await db
      .select({ name: campaigns.name })
      .from(campaigns)
      .where(and(inOrg(campaigns), eq(campaigns.id, id)))
      .limit(1);

    if (!campaign) {
      return NextResponse.json({ ok: false, error: "Campaign not found" }, { status: 404 });
    }

    const filename = campaignLeadTemplateFilename(campaign.name);
    const buffer = buildLeadsTemplateBuffer();

    return new NextResponse(new Uint8Array(buffer), {
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": `attachment; filename="${filename}"`,
      },
    });
  });
}
