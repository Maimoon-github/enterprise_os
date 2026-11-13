import { and, inArray, lt, isNotNull, or } from "drizzle-orm";
import { db } from "@/lib/db";
import { jobRuns, linkedInAccounts, webhookEvents } from "@/lib/linkedin/schema";
import { organizations } from "@/lib/auth/schema";
import { inOrg, runInOrganization } from "@/lib/tenancy/scope";

/**
 * How long job history and webhook events are kept. Both are only useful for debugging
 * a recent run; at ~50 job runs and ~300 webhook events a day they grow to hundreds of
 * megabytes within weeks, on a database shared with another product.
 */
const HISTORY_RETENTION_DAYS = 1;

const retentionCutoff = (): Date =>
  new Date(Date.now() - HISTORY_RETENTION_DAYS * 24 * 60 * 60 * 1000);

/**
 * Delete job runs past the retention window. JobLog rows cascade with them.
 *
 * Runs still marked RUNNING are only dropped once they are well past the window — a
 * crashed job leaves its status RUNNING forever, so filtering on finishedAt alone would
 * keep those rows (and their logs) indefinitely.
 */
export const pruneJobHistory = async (): Promise<void> => {
  const staleCutoff = new Date(Date.now() - (HISTORY_RETENTION_DAYS + 1) * 24 * 60 * 60 * 1000);

  const deleted = await db
    .delete(jobRuns)
    .where(
      or(
        and(lt(jobRuns.startedAt, retentionCutoff()), isNotNull(jobRuns.finishedAt)),
        lt(jobRuns.startedAt, staleCutoff)
      )
    )
    .returning({ id: jobRuns.id });

  console.log(
    `[resetDailyLimits] Pruned ${deleted.length} job run(s) older than ${HISTORY_RETENTION_DAYS} day(s)`
  );
};

/**
 * Delete only terminal webhook events past the retention window. Retryable,
 * abandoned, and dead-letter rows are durable inbox state and must survive until
 * replay or explicit reconciliation.
 */
const pruneWebhookEvents = async (): Promise<void> => {
  const deleted = await db
    .delete(webhookEvents)
    .where(and(
      inOrg(webhookEvents),
      lt(webhookEvents.createdAt, retentionCutoff()),
      inArray(webhookEvents.processingStatus, ["ok", "skipped"]),
    ))
    .returning({ id: webhookEvents.id });

  console.log(
    `[resetDailyLimits] Pruned ${deleted.length} webhook event(s) older than ${HISTORY_RETENTION_DAYS} day(s)`
  );
};

export type ResetDailyLimitsOptions = {
  /** Restrict the reset to one organization (a signed-in caller); omitted by cron, which serves every organization. */
  organizationId?: string;
  /**
   * Cron only: reset just these organizations (the rest already rolled over
   * today, src/lib/scheduler/dailyRollover.ts). Shared history is still pruned.
   */
  organizationIds?: string[];
};

export const resetDailyLimits = async (options: ResetDailyLimitsOptions = {}): Promise<void> => {
  console.log("[resetDailyLimits] Starting job");

  // JobRun / JobLog are shared by every organization; accounts and webhook
  // events are not, so each organization's are reset and pruned in its own scope.
  const organizationIds = options.organizationId
    ? [options.organizationId]
    : options.organizationIds ?? (await db.select({ id: organizations.id }).from(organizations)).map((org) => org.id);
  for (const organizationId of organizationIds) {
    await runInOrganization(organizationId, async () => {
      const updated = await db
        .update(linkedInAccounts)
        .set({ limitReached: false, searchLeadsToday: 0, profilePictureUrl: null })
        .where(inOrg(linkedInAccounts))
        .returning({ id: linkedInAccounts.id });

      console.log(
        `[resetDailyLimits] Reset limitReached and searchLeadsToday for ${updated.length} account(s)`
      );
      await pruneWebhookEvents();
    });
  }

  // Shared history: only the cron prunes it.
  if (!options.organizationId) await pruneJobHistory();
};
