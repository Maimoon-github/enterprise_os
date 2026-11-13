import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse } from "@/lib/auth/context";
import { replayLinkedinWebhooks } from "@/jobs/replayLinkedinWebhooks";
import { withJobTracking } from "@/lib/linkedin/jobTracker";
import { resolveJobCaller } from "@/lib/linkedin/organizations.server";
import { runPlatformJobForCron } from "@/lib/scheduler/endpoint";

export async function POST(req: NextRequest) {
  try {
    // The cron replays every organization's deliveries (once per slot, shared
    // with the in-process scheduler); a signed-in member only their own.
    const { organizationId } = await resolveJobCaller(req);
    if (!organizationId) return await runPlatformJobForCron("linkedin-replay-webhooks", req);
    let summary: Awaited<ReturnType<typeof replayLinkedinWebhooks>> | null = null;
    const runId = await withJobTracking("replay-linkedin-webhooks", async () => {
      summary = await replayLinkedinWebhooks(100, organizationId);
    });
    return NextResponse.json({ ok: true, runId, summary });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
