/**
 * Per-domain qualification pipeline.
 *
 * Flow (cheapest checks first):
 *   1. Live check — HTTP fetch; dead stores stop here.
 *   2. Parent lookup — Azure OpenAI resolves the parent company domain.
 *   3. Parent dedup/insert — if parent not yet in targeted_domains, insert it
 *      so it gets its own Apollo check; either way store parentId on this row.
 *   4. Apollo counts — query this domain. If a parent was newly discovered,
 *      query the parent separately and update the parent row too:
 *        allLeadCount    = total_entries (no email filter)  → "does Apollo have data?"
 *        verifiedLeadCount = total_entries (verified email) → qualification signal
 *   5. Decision:
 *        verifiedLeads >= 10           → qualified
 *        allLeads > 0, verified < 10   → apollo_has_data  (data exists, no verified emails)
 *        allLeads == 0                 → apollo_no_data
 */
import { and, eq, sql } from "drizzle-orm";
import { db } from "../db";
import { cleanDomains } from "../schema";
import { targetedDomains } from "./schema";
import { QUALIFICATION_CONFIG, STICKY_STATUSES } from "./config";
import { checkLiveness } from "./liveness";
import { countLeadsWithDebug } from "./apollo";
import { resolveParentDomainWithDebug } from "./parentLookup";
import { normalizeDomainForTargeting } from "./domain";
import type { QualificationResult, QualificationStatus } from "./types";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";

interface QualifyOptions {
  campaignId?: string;
  force?: boolean;
  isParentCompany?: boolean;
}

function emptyResult(domain: string): QualificationResult {
  return {
    domain,
    status: "pending",
    isLive: false,
    isParentCompany: false,
    allLeadCount: null,
    verifiedEmployeeCount: null,
    revenue: null,
    parentId: null,
    parentDomain: null,
    parentPreviouslyAdded: false,
    parentCampaignId: null,
    parentPending: false,
    reason: null,
    qualificationDebug: null,
  };
}

async function getCached(domain: string) {
  const rows = await db
    .select()
    .from(targetedDomains)
    .where(and(inOrg(targetedDomains), eq(targetedDomains.domain, domain)))
    .limit(1);
  return rows[0] ?? null;
}

/** Revenue (annual_sales) for a domain from clean_domains, if we have it. */
async function lookupRevenue(domain: string): Promise<string | null> {
  const rows = await db
    .select({ annualSales: cleanDomains.annualSales })
    .from(cleanDomains)
    .where(sql`regexp_replace(lower(${cleanDomains.domain}), '^www\\.', '') = ${domain}`)
    .limit(1);
  return rows[0]?.annualSales ?? null;
}

function isCacheFresh(status: string, checkedAt: Date | null): boolean {
  if (status === "pending") return false;
  if (status === "not_live") return false;
  if (STICKY_STATUSES.has(status)) return true;
  if (!checkedAt) return false;
  return Date.now() - checkedAt.getTime() < QUALIFICATION_CONFIG.recheckTtlMs;
}

async function persist(result: QualificationResult, campaignId?: string) {
  const values = {
    organizationId: currentOrganizationId(),
    domain: result.domain,
    campaignId: campaignId ?? null,
    status: result.status,
    isParentCompany: result.isParentCompany,
    isLive: result.isLive,
    allLeadCount: result.allLeadCount,
    verifiedEmployeeCount: result.verifiedEmployeeCount,
    revenue: result.revenue,
    parentId: result.parentId,
    parentDomain: result.parentDomain,
    parentPending: result.parentPending,
    reason: result.reason,
    qualificationDebug: result.qualificationDebug,
    checkedAt: new Date(),
  };
  await db
    .insert(targetedDomains)
    .values(values)
    .onConflictDoUpdate({ target: [targetedDomains.organizationId, targetedDomains.domain], set: values });
}

/**
 * Ensure a parent domain has a row in targeted_domains and report whether it
 * already existed before this qualification run.
 */
async function upsertParentRowWithState(
  parentDomain: string,
  campaignId?: string,
): Promise<{ id: string; alreadyTargeted: boolean; campaignId: string | null }> {
  const normalizedParentDomain = normalizeDomainForTargeting(parentDomain);
  const existing = await getCached(normalizedParentDomain);
  if (existing) {
    if (!existing.isParentCompany) {
      await db
        .update(targetedDomains)
        .set({ isParentCompany: true })
        .where(and(inOrg(targetedDomains), eq(targetedDomains.id, existing.id)));
    }
    return {
      id: existing.id,
      alreadyTargeted: true,
      campaignId: existing.campaignId ?? null,
    };
  }

  const inserted = await db
    .insert(targetedDomains)
    .values({
      organizationId: currentOrganizationId(),
      domain: normalizedParentDomain,
      campaignId: campaignId ?? null,
      status: "pending",
      isParentCompany: true,
      isLive: null,
      allLeadCount: null,
      verifiedEmployeeCount: null,
      parentId: null,
      parentDomain: null,
      parentPending: false,
      reason: null,
      qualificationDebug: null,
      checkedAt: new Date(),
    })
    .onConflictDoNothing()
    .returning({ id: targetedDomains.id, campaignId: targetedDomains.campaignId });

  if (inserted[0]) {
    return {
      id: inserted[0].id,
      alreadyTargeted: false,
      campaignId: inserted[0].campaignId ?? null,
    };
  }
  // Race condition: another request inserted it between our check and insert.
  const race = await getCached(normalizedParentDomain);
  return {
    id: race!.id,
    alreadyTargeted: true,
    campaignId: race!.campaignId ?? null,
  };
}

function decideApolloStatus(allLeads: number, verifiedLeads: number): QualificationStatus {
  if (verifiedLeads >= QUALIFICATION_CONFIG.minVerifiedEmployees) return "qualified";
  if (allLeads > 0) return "apollo_has_data";
  return "apollo_no_data";
}

function apolloReason(domain: string, allLeads: number, verifiedLeads: number) {
  if (verifiedLeads >= QUALIFICATION_CONFIG.minVerifiedEmployees) {
    return `${verifiedLeads} verified-email leads on Apollo`;
  }
  if (allLeads > 0) {
    return `${allLeads} total leads but only ${verifiedLeads} verified for ${domain}`;
  }
  return `no Apollo data for ${domain}`;
}

export async function qualifyDomain(
  domain: string,
  opts: QualifyOptions = {},
): Promise<QualificationResult> {
  const normalizedDomain = normalizeDomainForTargeting(domain);
  const result = emptyResult(normalizedDomain);
  const cached = await getCached(normalizedDomain);
  const isParentCompany = opts.isParentCompany ?? cached?.isParentCompany ?? false;
  result.isParentCompany = isParentCompany;

  // 0. Cache short-circuit.
  if (!opts.force) {
    if (cached && isCacheFresh(cached.status, cached.checkedAt ?? null)) {
      return {
        domain: normalizedDomain,
        status: cached.status as QualificationStatus,
        isLive: cached.isLive ?? false,
        isParentCompany: cached.isParentCompany ?? false,
        allLeadCount: cached.allLeadCount ?? null,
        verifiedEmployeeCount: cached.verifiedEmployeeCount ?? null,
        revenue: cached.revenue ?? null,
        parentId: cached.parentId ?? null,
        parentDomain: cached.parentDomain ?? null,
        parentPreviouslyAdded: false,
        parentCampaignId: null,
        parentPending: cached.parentPending ?? false,
        reason: cached.reason ?? null,
        qualificationDebug: cached.qualificationDebug ?? null,
      };
    }
  }

  // 1. Liveness. Parent-company rows are not Shopify shops, so they skip the
  // storefront/live check and go directly to Apollo. Revenue comes from our
  // own storefront data (clean_domains); parent companies aren't in that
  // table, so they inherit the child's revenue once one is discovered below.
  if (isParentCompany) {
    result.isLive = true;
    result.revenue = cached?.revenue ?? null;
  } else {
    result.revenue = await lookupRevenue(normalizedDomain);
    const live = await checkLiveness(normalizedDomain);
    result.isLive = live.isLive;
    if (!live.isLive) {
      result.status = "not_live";
      result.reason = live.reason ?? "not live";
      await persist(result, opts.campaignId);
      return result;
    }
  }

  // 2. Parent domain lookup via Azure OpenAI.
  const parentLookup = isParentCompany
    ? null
    : await resolveParentDomainWithDebug(normalizedDomain);
  const resolvedParent = parentLookup?.parentDomain
    ? normalizeDomainForTargeting(parentLookup.parentDomain)
    : null;
  if (parentLookup) {
    result.qualificationDebug = {
      parentLookup: parentLookup.debug,
    };
  }

  // 3. Dedup / insert the parent row and link it.
  let parentAlreadyTargeted = false;
  if (resolvedParent && resolvedParent !== normalizedDomain) {
    const parentRow = await upsertParentRowWithState(resolvedParent, opts.campaignId);
    result.parentId = parentRow.id;
    result.parentDomain = resolvedParent;
    result.parentPreviouslyAdded = parentRow.alreadyTargeted;
    result.parentCampaignId = parentRow.campaignId;
    parentAlreadyTargeted = parentRow.alreadyTargeted;
  } else if (resolvedParent === normalizedDomain) {
    result.parentPending = false;
  }

  // 4. Apollo counts — query the child domain on its own.
  const { allLeads, verifiedLeads, debug: childApolloDebug } =
    await countLeadsWithDebug(normalizedDomain);
  result.allLeadCount = allLeads;
  result.verifiedEmployeeCount = verifiedLeads;
  result.qualificationDebug = {
    ...result.qualificationDebug,
    apollo: {
      ...result.qualificationDebug?.apollo,
      child: childApolloDebug,
    },
  };

  // 4b. If this run created a parent row, run a separate parent Apollo lookup
  // and store the result on that parent row for full auditability.
  if (resolvedParent && result.parentId && !parentAlreadyTargeted) {
    const {
      allLeads: parentAllLeads,
      verifiedLeads: parentVerifiedLeads,
      debug: parentApolloDebug,
    } = await countLeadsWithDebug(resolvedParent);
    const parentStatus = decideApolloStatus(parentAllLeads, parentVerifiedLeads);
    const parentDebug = {
      apollo: {
        child: parentApolloDebug,
      },
    };

    result.qualificationDebug = {
      ...result.qualificationDebug,
      apollo: {
        ...result.qualificationDebug?.apollo,
        parent: parentApolloDebug,
      },
    };

    await db
      .update(targetedDomains)
      .set({
        status: parentStatus,
        isParentCompany: true,
        isLive: true,
        allLeadCount: parentAllLeads,
        verifiedEmployeeCount: parentVerifiedLeads,
        // Parent companies aren't in clean_domains, so they inherit the
        // discovering child's revenue rather than having their own.
        revenue: result.revenue,
        parentPending: false,
        reason: `parent lookup from ${normalizedDomain}: ${apolloReason(
          resolvedParent,
          parentAllLeads,
          parentVerifiedLeads,
        )}`,
        qualificationDebug: parentDebug,
        checkedAt: new Date(),
      })
      .where(and(inOrg(targetedDomains), eq(targetedDomains.id, result.parentId)));
  }

  // 5. Qualification decision.
  const parentReason = result.parentDomain
    ? `; parent: ${resolvedParent}${parentAlreadyTargeted ? " (previously added)" : ""}`
    : resolvedParent === normalizedDomain
      ? "; parent same as domain"
    : "";

  if (verifiedLeads >= QUALIFICATION_CONFIG.minVerifiedEmployees) {
    result.status = "qualified";
    result.reason = `${verifiedLeads} verified-email leads on Apollo${parentReason}`;
  } else if (allLeads > 0) {
    result.status = "apollo_has_data";
    result.parentPending = !resolvedParent;
    result.reason = `${allLeads} total leads but only ${verifiedLeads} verified${parentReason || "; parent unknown"}`;
  } else {
    result.status = "apollo_no_data";
    result.parentPending = !resolvedParent;
    result.reason = `no Apollo data for ${normalizedDomain}${parentReason}`;
  }

  await persist(result, opts.campaignId);
  return result;
}
