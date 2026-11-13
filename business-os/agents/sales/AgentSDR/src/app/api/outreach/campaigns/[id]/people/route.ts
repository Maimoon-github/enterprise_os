import { NextRequest, NextResponse } from "next/server";
import { addPeopleToEmailCampaign } from "@/lib/leads/campaignAssignments";
import { getCampaign } from "@/lib/outreach/campaigns";
import { withOrgContext, authContextErrorResponse } from "@/lib/auth/context";

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withOrgContext(req, async () => {
      const { id } = await params;
      const body = await req.json().catch(() => null);
      if (!body || !Array.isArray(body.personIds) || body.personIds.some((id: unknown) => typeof id !== "string")) {
        return NextResponse.json({ error: "personIds must be an array of IDs" }, { status: 400 });
      }
      if (!(await getCampaign(id))) return NextResponse.json({ error: "not found" }, { status: 404 });
      try {
        return NextResponse.json(await addPeopleToEmailCampaign(id, body.personIds));
      } catch (error) {
        return NextResponse.json({ error: error instanceof Error ? error.message : "Could not add people" }, { status: 400 });
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
