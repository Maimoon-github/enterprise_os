import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse } from "@/lib/auth/context";
import { resetDailyLimits } from "@/jobs/resetDailyLimits";
import { withJobTracking } from "@/lib/linkedin/jobTracker";
import { resolveJobCaller } from "@/lib/linkedin/organizations.server";
import { cronOrganizationFilter } from "@/lib/scheduler/endpoint";

export async function POST(req: NextRequest) {
  try {
    // A signed-in member resets only their own organization. The cron resets
    // every organization — except, while the in-process scheduler runs, those
    // whose daily rollover (which includes this reset) already ran today.
    const { organizationId } = await resolveJobCaller(req);
    if (organizationId) {
      const runId = await withJobTracking("reset-daily-limits", () => resetDailyLimits({ organizationId }));
      return NextResponse.json({ ok: true, runId });
    }
    const { organizationIds, alreadyRolledOver } = await cronOrganizationFilter(req);
    const runId = await withJobTracking("reset-daily-limits", () => resetDailyLimits({ organizationIds }));
    return NextResponse.json({ ok: true, runId, ...(alreadyRolledOver ? { alreadyRolledOver } : {}) });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
