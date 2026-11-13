import { NextRequest, NextResponse } from "next/server";
import { and, eq, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { campaigns, qualificationJobs } from "@/lib/schema";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { inOrg } from "@/lib/tenancy/scope";

// POST /api/campaigns/[id]/stop
// Marks active qualification jobs for this campaign so the stream loop exits
// after the currently processed domain completes.
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    return await withOrgContext(req, async () => {
      // qualification_jobs inherit scope from the campaign.
      const stopped = await db
        .update(qualificationJobs)
        .set({ status: "cancel_requested" })
        .where(
          and(
            inArray(qualificationJobs.campaignId, db.select({ id: campaigns.id }).from(campaigns).where(and(inOrg(campaigns), eq(campaigns.id, id)))),
            inArray(qualificationJobs.status, ["running", "cancel_requested"]),
          ),
        )
        .returning({ id: qualificationJobs.id });

      return NextResponse.json({ stopRequested: stopped.length > 0 });
    });
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}
