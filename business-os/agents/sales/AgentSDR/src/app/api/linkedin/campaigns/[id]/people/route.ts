import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { addPeopleToLinkedinCampaign } from "@/lib/leads/campaignAssignments";

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(req, async () => {
    const { id } = await params;
    const body = await req.json().catch(() => null);
    if (!body || !Array.isArray(body.personIds) || body.personIds.some((personId: unknown) => typeof personId !== "string")) {
      return NextResponse.json({ error: "personIds must be an array of IDs" }, { status: 400 });
    }
    try {
      const result = await addPeopleToLinkedinCampaign(id, body.personIds, {
        ...(typeof body.invitationMessage === "string" && { invitationMessage: body.invitationMessage }),
        ...(typeof body.acceptanceMessage === "string" && { acceptanceMessage: body.acceptanceMessage }),
        ...(typeof body.followUp1Message === "string" && { followUp1Message: body.followUp1Message }),
        ...(typeof body.followUp2Message === "string" && { followUp2Message: body.followUp2Message }),
        ...(typeof body.followUp3Message === "string" && { followUp3Message: body.followUp3Message }),
      });
      return NextResponse.json(result);
    } catch (error) {
      return NextResponse.json({ error: error instanceof Error ? error.message : "Could not add people" }, { status: 400 });
    }
  });
}
