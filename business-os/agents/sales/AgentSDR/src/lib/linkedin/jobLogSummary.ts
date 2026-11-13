import { count, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { jobLogs } from "@/lib/linkedin/schema";

export const jobLogSummaryByRunIds = async (runIds: string[]) => {
  if (runIds.length === 0) return {};

  const groups = await db
    .select({ jobRunId: jobLogs.jobRunId, level: jobLogs.level, count: count() })
    .from(jobLogs)
    .where(inArray(jobLogs.jobRunId, runIds))
    .groupBy(jobLogs.jobRunId, jobLogs.level);

  const map: Record<string, { total: number; warn: number; error: number }> = {};
  for (const g of groups) {
    if (!map[g.jobRunId]) map[g.jobRunId] = { total: 0, warn: 0, error: 0 };
    map[g.jobRunId].total += g.count;
    if (g.level === "warn") map[g.jobRunId].warn += g.count;
    if (g.level === "error") map[g.jobRunId].error += g.count;
  }
  return map;
};
