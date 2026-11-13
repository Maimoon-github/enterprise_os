import { NextResponse } from "next/server";
import { requirePlatformOperator } from "@/lib/auth/context";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { asc, desc, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { jobLogs, jobRuns } from "@/lib/linkedin/schema";

export async function GET(req: Request) {
  // Job runs and logs span every organization's accounts: operator only.
  return withLinkedinOrg(req, async (ctx) => {
    await requirePlatformOperator(ctx);
    const runRows = await db
      .select()
      .from(jobRuns)
      .orderBy(desc(jobRuns.startedAt))
      .limit(100);

    // Replaces `include: { logs: { orderBy: { createdAt: "asc" } } }` — one
    // query for the logs of the runs on this page, regrouped by run.
    const runIds = runRows.map((r) => r.id);
    const logRows = runIds.length
      ? await db
          .select()
          .from(jobLogs)
          .where(inArray(jobLogs.jobRunId, runIds))
          .orderBy(asc(jobLogs.createdAt))
      : [];

    const logsByRunId = new Map<string, typeof logRows>();
    for (const log of logRows) {
      const list = logsByRunId.get(log.jobRunId) ?? [];
      list.push(log);
      logsByRunId.set(log.jobRunId, list);
    }

    const runs = runRows.map((r) => ({ ...r, logs: logsByRunId.get(r.id) ?? [] }));

    return NextResponse.json({ ok: true, runs });
  });
}
