import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse } from "@/lib/auth/context";
import { runOutreach } from "@/jobs/runOutreach";
import { withJobTracking } from "@/lib/linkedin/jobTracker";
import { resolveJobCaller } from "@/lib/linkedin/organizations.server";
import { runPlatformJobForCron } from "@/lib/scheduler/endpoint";

export async function POST(req: NextRequest) {
  try {
    // The cron runs every organization (once per slot, shared with the
    // in-process scheduler); a signed-in member runs their own.
    const { organizationId } = await resolveJobCaller(req);
    if (!organizationId) return await runPlatformJobForCron("linkedin-run-outreach", req);
    const runId = await withJobTracking("run-outreach", () => runOutreach({ organizationId }));
    return NextResponse.json({ ok: true, runId });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
