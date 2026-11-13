import { NextResponse } from "next/server";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { deleteCampaign } from "@/lib/qualification";

// DELETE /api/campaigns/[id]
// Removes the campaign, its jobs, its targeted domains, and parent rows
// referenced by those targeted domains via parent_id.
export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    return await withOrgContext(req, async () => {
      const result = await deleteCampaign(id);

      if (!result.campaignDeleted) {
        return NextResponse.json({ error: "campaign not found" }, { status: 404 });
      }

      return NextResponse.json(result);
    });
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}
