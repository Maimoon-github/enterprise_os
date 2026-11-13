import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";
import { resolveJobCaller } from "@/lib/linkedin/organizations.server";
import { unknownAccountIds } from "@/lib/linkedin/searchBatches";
import { and, eq } from "drizzle-orm";
import { runSearchQueue } from "@/jobs/runSearchQueue";
import { withJobTracking } from "@/lib/linkedin/jobTracker";
import { db } from "@/lib/db";
import { jobRuns } from "@/lib/linkedin/schema";
import { runPlatformJobForCron } from "@/lib/scheduler/endpoint";

const isStringArray = (v: unknown): v is string[] => Array.isArray(v) && v.every((id) => typeof id === "string" && id);

export async function POST(req: NextRequest) {
  try {
    // The cron works every organization's queue; a signed-in member only their own.
    const { organizationId } = await resolveJobCaller(req);
    return organizationId ? await runInOrganization(organizationId, () => handle(req, true)) : await handle(req, false);
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

async function handle(req: NextRequest, scoped: boolean) {
  // An omitted or empty `accountIds` means "use every connected account", which is what
  // the plain button click has always meant.
  const raw = await req.text();
  const body: unknown = raw ? JSON.parse(raw) : {};
  const accountIds =
    typeof body === "object" && body !== null && "accountIds" in body ? (body as { accountIds: unknown }).accountIds : undefined;
  if (accountIds !== undefined && !isStringArray(accountIds)) {
    return NextResponse.json({ ok: false, error: "accountIds must be an array of account ids" }, { status: 400 });
  }
  // Account ids are only meaningful inside one organization: refuse any that are not the
  // caller's (and any at all from the cron, which has no organization).
  if (accountIds?.length && (!scoped || (await unknownAccountIds(accountIds)).length > 0)) {
    return NextResponse.json({ ok: false, error: "Unknown account" }, { status: 400 });
  }

  // The cron: the same run the in-process scheduler would start (deduped
  // against its slot once that job is enabled in src/lib/scheduler/schedules.ts).
  if (!scoped) return runPlatformJobForCron("linkedin-run-search-queue", req);

  // runSearchQueue itself refuses to run alongside another active run, but checking here
  // too avoids spamming Job History with a no-op JobRun on every extra click.
  // JobRun is shared by every organization, so this lock is global by design.
  const [alreadyRunning] = await db
    .select()
    .from(jobRuns)
    .where(and(eq(jobRuns.job, "run-search-queue"), eq(jobRuns.status, "RUNNING")))
    .limit(1);
  if (alreadyRunning) {
    return NextResponse.json({ ok: true, runId: alreadyRunning.id, alreadyRunning: true });
  }

  const runId = await withJobTracking("run-search-queue", (id) => runSearchQueue(id, { accountIds }));
  return NextResponse.json({ ok: true, runId });
}
