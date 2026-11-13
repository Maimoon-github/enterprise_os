// deployment test
import { and, desc, eq, inArray, isNull } from "drizzle-orm";
import { db } from "../db";
import { campaigns, qualificationJobs } from "./schema";
import { currentOrganizationId, inOrg, maybeCurrentOrganizationId, runInOrganization } from "@/lib/tenancy/scope";
import {
  assembleApolloLink,
  getCampaignDomains,
  listPendingCandidates,
  selectCandidates,
} from "./campaigns";
import { qualifyDomain } from "./qualify";
import type { CampaignFilters } from "./types";

/**
 * Job ids are globally unique uuids, so these process-wide maps cannot mix
 * organizations; each job still runs inside runInOrganization(its campaign's
 * organization), resolved from the data, never from whoever restarts it.
 */
const runningJobs = new Map<string, Promise<void>>();
const STALE_JOB_MS = 2 * 60 * 1000;
/** Concurrent workers per job. Apollo/Azure limits comfortably cover this. */
const CONCURRENCY = 10;
/** Auto-restart attempts for a job that dies from an infra error, before giving up for good. */
const MAX_AUTO_RETRIES = 5;
const retryCounts = new Map<string, number>();

export async function getActiveCampaignJob(campaignId: string) {
  // qualification_jobs inherit their scope from the campaign.
  const [row] = await db
    .select({ job: qualificationJobs })
    .from(qualificationJobs)
    .innerJoin(campaigns, eq(campaigns.id, qualificationJobs.campaignId))
    .where(
      and(
        inOrg(campaigns),
        eq(qualificationJobs.campaignId, campaignId),
        inArray(qualificationJobs.status, ["running", "cancel_requested"]),
        isNull(qualificationJobs.finishedAt),
      ),
    )
    .orderBy(desc(qualificationJobs.startedAt))
    .limit(1);
  return row?.job ?? null;
}

export async function startCampaignJob(campaignId: string, limit: number) {
  const organizationId = currentOrganizationId();
  const [campaign] = await db.select({ id: campaigns.id }).from(campaigns).where(and(inOrg(campaigns), eq(campaigns.id, campaignId))).limit(1);
  if (!campaign) throw new Error(`campaign ${campaignId} not found`);
  const active = await getActiveCampaignJob(campaignId);
  if (active) {
    runJobInBackground(active.id, organizationId);
    return active;
  }

  const [job] = await db
    .insert(qualificationJobs)
    .values({
      campaignId,
      status: "running",
      requestedLimit: limit,
      lastHeartbeatAt: new Date(),
    })
    .returning();

  runJobInBackground(job.id, organizationId);
  return job;
}

export async function resumeCampaignJobIfNeeded(campaignId: string) {
  const active = await getActiveCampaignJob(campaignId);
  if (!active) return null;
  runJobInBackground(active.id, currentOrganizationId());
  return active;
}

/**
 * Restart jobs that need it: ones stuck in "running" with no live in-process
 * worker (e.g. after a server restart), and ones that died with "failed" from
 * an infra error rather than a deliberate stop — up to MAX_AUTO_RETRIES each,
 * continuing from their persisted domainsProcessed/domainsQualified rather
 * than starting the candidate list over.
 */
export async function recoverStaleJobs() {
  // A global sweep with no session: every job carries the organization of its
  // campaign, and is restarted inside that organization's scope.
  // Inside a request scope (the run/stream routes call this) it only touches
  // that organization's jobs; with no scope it sweeps every organization.
  const scopedTo = maybeCurrentOrganizationId();
  const inScope = scopedTo ? eq(campaigns.organizationId, scopedTo) : undefined;
  const cutoff = new Date(Date.now() - STALE_JOB_MS);
  const staleJobs = await db
    .select({ id: qualificationJobs.id, organizationId: campaigns.organizationId })
    .from(qualificationJobs)
    .innerJoin(campaigns, eq(campaigns.id, qualificationJobs.campaignId))
    .where(
      and(
        inScope,
        eq(qualificationJobs.status, "running"),
        isNull(qualificationJobs.finishedAt),
      ),
    );

  for (const job of staleJobs) {
    if (!runningJobs.has(job.id)) runJobInBackground(job.id, job.organizationId);
  }

  await db
    .update(qualificationJobs)
    .set({ lastHeartbeatAt: new Date() })
    .where(
      and(
        scopedTo
          ? inArray(qualificationJobs.campaignId, db.select({ id: campaigns.id }).from(campaigns).where(eq(campaigns.organizationId, scopedTo)))
          : undefined,
        eq(qualificationJobs.status, "running"),
        isNull(qualificationJobs.lastHeartbeatAt),
      ),
    );

  const failedJobs = await db
    .select({ id: qualificationJobs.id, organizationId: campaigns.organizationId })
    .from(qualificationJobs)
    .innerJoin(campaigns, eq(campaigns.id, qualificationJobs.campaignId))
    .where(and(inScope, eq(qualificationJobs.status, "failed")));

  for (const job of failedJobs) {
    if (runningJobs.has(job.id)) continue;
    const attempts = retryCounts.get(job.id) ?? 0;
    if (attempts >= MAX_AUTO_RETRIES) continue;
    retryCounts.set(job.id, attempts + 1);
    await db
      .update(qualificationJobs)
      .set({ status: "running", finishedAt: null, lastHeartbeatAt: new Date() })
      .where(eq(qualificationJobs.id, job.id));
    runJobInBackground(job.id, job.organizationId);
  }

  return cutoff;
}

function runJobInBackground(jobId: string, organizationId: string) {
  const existing = runningJobs.get(jobId);
  if (existing) return existing;

  const promise = runInOrganization(organizationId, () => processCampaignJob(jobId))
    .catch((error) => {
      console.error(`qualification job ${jobId} failed`, error);
    })
    .finally(() => {
      runningJobs.delete(jobId);
    });

  runningJobs.set(jobId, promise);
  return promise;
}

async function processCampaignJob(jobId: string) {
  const job = await getJob(jobId);
  if (!job || job.finishedAt) return;
  if (job.status === "cancel_requested") {
    await markCancelled(jobId, job.domainsProcessed, job.domainsQualified);
    return;
  }

  const [campaign] = await db
    .select()
    .from(campaigns)
    .where(and(inOrg(campaigns), eq(campaigns.id, job.campaignId)))
    .limit(1);
  if (!campaign) {
    await markFailed(jobId, job.domainsProcessed, job.domainsQualified, null);
    return;
  }

  // "domains" mode: the campaign target IS the batch size — fetch exactly
  // that many top candidates and work through all of them, qualified or not.
  // "leads" mode: keep pulling up to requestedLimit candidates per run,
  // stopping early once enough verified leads have accumulated.
  const limit =
    campaign.targetMode === "domains"
      ? campaign.targetDomainCount ?? 150
      : job.requestedLimit ?? 200;
  const candidates =
    campaign.inputMode === "manual"
      ? await listPendingCandidates(job.campaignId)
      : await selectCandidates((campaign.filters as CampaignFilters) ?? {}, limit);

  let processed = job.domainsProcessed ?? 0;
  let qualified = job.domainsQualified ?? 0;
  let accumulated = campaign.accumulatedLeadCount ?? 0;
  let cancelled = false;
  let nextIndex = 0;
  const inFlight = new Map<number, string>(); // worker slot -> domain currently running

  // "domains" mode stops once the whole fetched batch has been processed —
  // it's a fixed-size analysis run, not a qualified-count goal. "leads" mode
  // keeps going until enough verified leads have accumulated.
  const targetReached = () =>
    campaign.targetMode === "domains"
      ? processed >= candidates.length
      : accumulated >= campaign.targetLeadCount;

  // Persist shared counters + heartbeat. Multiple workers finish domains
  // around the same time and all call this; chain onto the previous call so
  // DB writes happen in the same order the in-memory counters were updated
  // (otherwise a later, larger snapshot could be overwritten by an earlier,
  // smaller one landing out of order).
  let progressChain: Promise<void> = Promise.resolve();
  function persistProgress(): Promise<void> {
    progressChain = progressChain.then(async () => {
      await db
        .update(campaigns)
        .set({
          accumulatedLeadCount: accumulated,
          status: targetReached() ? "ready" : "building",
        })
        .where(and(inOrg(campaigns), eq(campaigns.id, job.campaignId)));

      await db
        .update(qualificationJobs)
        .set({
          domainsProcessed: processed,
          domainsQualified: qualified,
          currentDomain: [...inFlight.values()].join(", ") || null,
          lastHeartbeatAt: new Date(),
        })
        .where(eq(qualificationJobs.id, jobId));
    });
    return progressChain;
  }

  async function worker(slot: number) {
    while (true) {
      if (cancelled || targetReached()) return;
      const index = nextIndex;
      if (index >= candidates.length) return;
      nextIndex += 1;

      const candidate = candidates[index];
      inFlight.set(slot, candidate.domain);

      const result = await qualifyDomain(candidate.domain, { campaignId: job.campaignId }).catch(
        (error) => {
          console.error(`qualification failed for ${candidate.domain}`, error);
          return null;
        },
      );

      inFlight.delete(slot);

      // Everything past this point is bookkeeping (linking a discovered
      // parent, persisting counters, checking for cancellation). None of it
      // should be able to kill the whole batch — a transient DB error here
      // must not stop the other workers or orphan the job at a frozen count.
      try {
        if (result) {
          processed += 1;
          // Only a targeted candidate domain counts toward "N domains qualified" —
          // an incidentally-discovered parent company is a bonus, not one of the N.
          if (result.status === "qualified") {
            qualified += 1;
            accumulated += result.verifiedEmployeeCount ?? 0;
          }

          if (result.parentId && !result.parentPreviouslyAdded) {
            const parentRows = await getCampaignDomains(job.campaignId);
            const parentRow = parentRows.find((row) => row.id === result.parentId);
            if (parentRow?.status === "qualified") {
              accumulated += parentRow.verifiedEmployeeCount ?? 0;
              if (campaign.targetMode !== "domains") qualified += 1;
            }
          }
        }

        const freshJob = await getJob(jobId);
        if (!freshJob || freshJob.status === "cancel_requested") {
          cancelled = true;
        }

        await persistProgress();
      } catch (error) {
        console.error(`progress bookkeeping failed for ${candidate.domain}`, error);
      }
    }
  }

  try {
    const workerCount = Math.min(CONCURRENCY, candidates.length);
    await Promise.all(Array.from({ length: workerCount }, (_, i) => worker(i)));

    if (cancelled) {
      await markCancelled(jobId, processed, qualified);
      return;
    }

    let apolloLink: string | null = null;
    try {
      apolloLink = await assembleApolloLink(job.campaignId);
    } catch {
      // No qualified domains yet.
    }

    await db
      .update(campaigns)
      .set({
        accumulatedLeadCount: accumulated,
        apolloLink,
        status: targetReached() ? "ready" : "building",
      })
      .where(and(inOrg(campaigns), eq(campaigns.id, job.campaignId)));

    await db
      .update(qualificationJobs)
      .set({
        status: "success",
        domainsProcessed: processed,
        domainsQualified: qualified,
        currentDomain: null,
        lastHeartbeatAt: new Date(),
        finishedAt: new Date(),
      })
      .where(eq(qualificationJobs.id, jobId));
  } catch (error) {
    await markFailed(jobId, processed, qualified, null);
    throw error;
  }
}

/** The job, only if its campaign belongs to the organization in scope. */
async function getJob(jobId: string) {
  const [row] = await db
    .select({ job: qualificationJobs })
    .from(qualificationJobs)
    .innerJoin(campaigns, eq(campaigns.id, qualificationJobs.campaignId))
    .where(and(inOrg(campaigns), eq(qualificationJobs.id, jobId)))
    .limit(1);
  return row?.job ?? null;
}

async function markCancelled(jobId: string, processed: number, qualified: number) {
  await db
    .update(qualificationJobs)
    .set({
      status: "cancelled",
      domainsProcessed: processed,
      domainsQualified: qualified,
      currentDomain: null,
      lastHeartbeatAt: new Date(),
      finishedAt: new Date(),
    })
    .where(eq(qualificationJobs.id, jobId));
}

async function markFailed(
  jobId: string,
  processed: number,
  qualified: number,
  currentDomain: string | null,
) {
  await db
    .update(qualificationJobs)
    .set({
      status: "failed",
      domainsProcessed: processed,
      domainsQualified: qualified,
      currentDomain,
      lastHeartbeatAt: new Date(),
      finishedAt: new Date(),
    })
    .where(eq(qualificationJobs.id, jobId));
}
