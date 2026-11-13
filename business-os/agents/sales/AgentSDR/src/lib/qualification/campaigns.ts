/**
 * Campaign layer: create campaigns, select candidate domains (filters or manual),
 * run the qualification batch with global de-duplication and lead-target
 * accumulation, handle manual parent research, and assemble the final Apollo link.
 */
import { and, desc, eq, gte, isNull, lte, sql } from "drizzle-orm";
import { alias } from "drizzle-orm/pg-core";
import { db } from "../db";
import { cleanDomains } from "../schema";
import { NULL_CATEGORY } from "../queries";
import { campaigns, qualificationJobs, targetedDomains } from "./schema";
import { qualifyDomain } from "./qualify";
import { buildApolloPeopleSearchUrl } from "./apolloLink";
import { QUALIFICATION_CONFIG } from "./config";
import { normalizeDomainForTargeting } from "./domain";
import type { CampaignFilters, CampaignInputMode, CampaignTargetMode } from "./types";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";

interface CreateCampaignInput {
  name?: string;
  inputMode: CampaignInputMode;
  jobTitles?: string[];
  targetMode?: CampaignTargetMode;
  targetLeadCount?: number;
  targetDomainCount?: number;
  filters?: CampaignFilters;
}

const COUNTRY_LABELS: Record<string, string> = {
  US: "United States",
  GB: "United Kingdom",
  CA: "Canada",
  AU: "Australia",
  IN: "India",
  DE: "Germany",
};

function cleanNamePart(value: string | undefined): string | null {
  const cleaned = value?.trim();
  return cleaned ? cleaned : null;
}

function revenueLabel(minRevenue?: string, maxRevenue?: string) {
  if (minRevenue && maxRevenue) return `$${minRevenue}-${maxRevenue}`;
  if (minRevenue) return `$${minRevenue}+`;
  if (maxRevenue) return `up to $${maxRevenue}`;
  return null;
}

function baseCampaignName(input: CreateCampaignInput) {
  if (input.name?.trim()) return input.name.trim();

  if (input.inputMode === "manual") {
    return "Manual domains";
  }

  const filters = input.filters ?? {};
  const country = COUNTRY_LABELS[(filters.countryCode ?? "US").toUpperCase()] ?? filters.countryCode ?? "US";
  const parts = [
    country,
    cleanNamePart(filters.platform),
    cleanNamePart(filters.c1),
    cleanNamePart(filters.c2),
    cleanNamePart(filters.c3),
    cleanNamePart(filters.app),
    revenueLabel(filters.minRevenue, filters.maxRevenue),
  ].filter(Boolean);

  return parts.length > 0 ? parts.join(" · ") : "All filters";
}

async function uniqueCampaignName(input: CreateCampaignInput) {
  const baseName = baseCampaignName(input);
  const rows = await db
    .select({ name: campaigns.name })
    .from(campaigns)
    .where(and(inOrg(campaigns), sql`(${campaigns.name} = ${baseName} OR ${campaigns.name} LIKE ${`${baseName} (%)`})`));

  const existing = new Set(rows.map((row) => row.name));
  if (!existing.has(baseName)) return baseName;

  let suffix = 2;
  while (existing.has(`${baseName} (${suffix})`)) suffix += 1;
  return `${baseName} (${suffix})`;
}

export async function createCampaign(input: CreateCampaignInput) {
  const name = await uniqueCampaignName(input);
  const targetMode = input.targetMode ?? "leads";
  const [row] = await db
    .insert(campaigns)
    .values({
      organizationId: currentOrganizationId(),
      name,
      inputMode: input.inputMode,
      jobTitles: input.jobTitles ?? [],
      filters: input.filters ?? null,
      targetMode,
      targetLeadCount: input.targetLeadCount ?? QUALIFICATION_CONFIG.defaultLeadTarget,
      targetDomainCount:
        targetMode === "domains" ? input.targetDomainCount ?? 150 : null,
    })
    .returning();
  return row;
}

/**
 * Candidate domains for a filter campaign: clean_domains matching the filters,
 * EXCLUDING any domain already in targeted_domains (global dedup).
 */
export async function selectCandidates(
  filters: CampaignFilters,
  limit: number,
): Promise<{ domain: string; merchantName: string | null }[]> {
  const countryCode = (filters.countryCode ?? "US").toUpperCase();
  const conditions = [eq(cleanDomains.countryCode, countryCode)];

  if (filters.c1 === NULL_CATEGORY) conditions.push(isNull(cleanDomains.c1));
  else if (filters.c1) conditions.push(eq(cleanDomains.c1, filters.c1));
  if (filters.c2 === NULL_CATEGORY) conditions.push(isNull(cleanDomains.c2));
  else if (filters.c2) conditions.push(eq(cleanDomains.c2, filters.c2));
  if (filters.c3 === NULL_CATEGORY) conditions.push(isNull(cleanDomains.c3));
  else if (filters.c3) conditions.push(eq(cleanDomains.c3, filters.c3));
  if (filters.platform) conditions.push(eq(cleanDomains.platform, filters.platform));
  if (filters.app) {
    conditions.push(sql`${cleanDomains.installedAppsArray} @> ARRAY[${filters.app}]::text[]`);
  }
  if (filters.minRevenue) conditions.push(gte(cleanDomains.annualSales, filters.minRevenue));
  if (filters.maxRevenue) conditions.push(lte(cleanDomains.annualSales, filters.maxRevenue));

  conditions.push(
    sql`NOT EXISTS (
      SELECT 1
      FROM ${targetedDomains} td
      WHERE td.organization_id = ${currentOrganizationId()}
        AND td.domain = regexp_replace(lower(${cleanDomains.domain}), '^www\\.', '')
    )`,
  );

  const rows = await db
    .select({ domain: cleanDomains.domain, merchantName: cleanDomains.merchantName })
    .from(cleanDomains)
    .where(and(...conditions))
    .orderBy(sql`${cleanDomains.annualSales} DESC NULLS LAST`)
    .limit(limit);

  const seen = new Set<string>();
  return rows
    .map((row) => ({
      ...row,
      domain: normalizeDomainForTargeting(row.domain),
    }))
    .filter((row) => {
      if (seen.has(row.domain)) return false;
      seen.add(row.domain);
      return true;
    });
}

/**
 * Manual mode: confirm each pasted domain exists in our DB and isn't already
 * targeted. Returns the usable set plus rejects (with reasons).
 */
export async function lookupManualDomains(input: string[]): Promise<{
  found: string[];
  notFound: string[];
  alreadyTargeted: string[];
}> {
  const cleaned = [...new Set(input.map(normalizeDomainForTargeting).filter(Boolean))];
  const found: string[] = [];
  const notFound: string[] = [];
  const alreadyTargeted: string[] = [];

  for (const domain of cleaned) {
    const exists = await db
      .select({ domain: cleanDomains.domain })
      .from(cleanDomains)
      .where(sql`regexp_replace(lower(${cleanDomains.domain}), '^www\\.', '') = ${domain}`)
      .limit(1);
    if (exists.length === 0) {
      notFound.push(domain);
      continue;
    }
    const targeted = await db
      .select({ domain: targetedDomains.domain })
      .from(targetedDomains)
      .where(and(inOrg(targetedDomains), eq(targetedDomains.domain, domain)))
      .limit(1);
    if (targeted.length > 0) alreadyTargeted.push(domain);
    else found.push(domain);
  }

  return { found, notFound, alreadyTargeted };
}

/** Stage looked-up domains as `pending` rows for a manual campaign. */
export async function addManualCandidates(
  campaignId: string,
  domainsList: string[],
): Promise<number> {
  if (domainsList.length === 0) return 0;
  const normalizedDomains = [...new Set(domainsList.map(normalizeDomainForTargeting).filter(Boolean))];
  if (normalizedDomains.length === 0) return 0;
  if (!(await getCampaign(campaignId))) throw new Error(`campaign ${campaignId} not found`);
  const inserted = await db
    .insert(targetedDomains)
    .values(normalizedDomains.map((domain) => ({ organizationId: currentOrganizationId(), domain, campaignId, status: "pending" as const })))
    .onConflictDoNothing({ target: [targetedDomains.organizationId, targetedDomains.domain] })
    .returning({ domain: targetedDomains.domain });
  return inserted.length;
}

/** Staged-but-not-yet-qualified candidates for a campaign (manual mode). */
export async function listPendingCandidates(
  campaignId: string,
): Promise<{ domain: string }[]> {
  return db
    .select({ domain: targetedDomains.domain })
    .from(targetedDomains)
    .where(
      and(inOrg(targetedDomains), eq(targetedDomains.campaignId, campaignId), eq(targetedDomains.status, "pending")),
    );
}

/** Domains awaiting manual parent-company research. */
export async function listParentPending() {
  return db
    .select()
    .from(targetedDomains)
    .where(and(inOrg(targetedDomains), eq(targetedDomains.parentPending, true)));
}

/**
 * Manual parent research: a human supplies the parent domain for a low-data
 * child. We point the child at the parent, then add the parent as its own row
 * (deduped by domain) and qualify it. If the parent qualifies, it becomes the
 * targetable entity.
 */
export async function setParentDomain(childDomain: string, parentDomain: string) {
  const child = normalizeDomainForTargeting(childDomain);
  const parent = normalizeDomainForTargeting(parentDomain);

  const [childRow] = await db
    .select({ campaignId: targetedDomains.campaignId })
    .from(targetedDomains)
    .where(and(inOrg(targetedDomains), eq(targetedDomains.domain, child)))
    .limit(1);

  if (parent === child) {
    await db
      .update(targetedDomains)
      .set({ parentId: null, parentDomain: null, parentPending: false })
      .where(and(inOrg(targetedDomains), eq(targetedDomains.domain, child)));

    return { child, parent, parentResult: null };
  }

  const inserted = await db
    .insert(targetedDomains)
    .values({
      organizationId: currentOrganizationId(),
      domain: parent,
      campaignId: childRow?.campaignId ?? null,
      status: "pending" as const,
      isParentCompany: true,
    })
    .onConflictDoNothing({ target: [targetedDomains.organizationId, targetedDomains.domain] })
    .returning({ id: targetedDomains.id });

  const parentRow =
    inserted[0] ??
    (
      await db
        .select({ id: targetedDomains.id })
        .from(targetedDomains)
        .where(and(inOrg(targetedDomains), eq(targetedDomains.domain, parent)))
        .limit(1)
    )[0];

  await db
    .update(targetedDomains)
    .set({ parentId: parentRow?.id ?? null, parentDomain: parent, parentPending: false })
    .where(and(inOrg(targetedDomains), eq(targetedDomains.domain, child)));

  const parentResult = inserted[0]
    ? await qualifyDomain(parent, {
        campaignId: childRow?.campaignId ?? undefined,
        isParentCompany: true,
      })
    : null;
  return { child, parent, parentResult };
}

/** All campaigns, most recent first. */
export async function listCampaigns() {
  return db.select().from(campaigns).where(inOrg(campaigns)).orderBy(desc(campaigns.createdAt)).limit(100);
}

/** A single campaign by id. */
export async function getCampaign(id: string) {
  const [row] = await db.select().from(campaigns).where(and(inOrg(campaigns), eq(campaigns.id, id))).limit(1);
  return row ?? null;
}

/** The per-domain status table for a campaign (the audit view). */
export async function getCampaignDomains(campaignId: string) {
  const parentDomains = alias(targetedDomains, "parent_domains");

  return db
    .select({
      id: targetedDomains.id,
      domain: targetedDomains.domain,
      campaignId: targetedDomains.campaignId,
      status: targetedDomains.status,
      isParentCompany: targetedDomains.isParentCompany,
      isLive: targetedDomains.isLive,
      allLeadCount: targetedDomains.allLeadCount,
      verifiedEmployeeCount: targetedDomains.verifiedEmployeeCount,
      revenue: targetedDomains.revenue,
      parentId: targetedDomains.parentId,
      parentDomain: targetedDomains.parentDomain,
      parentCampaignId: parentDomains.campaignId,
      parentPending: targetedDomains.parentPending,
      reason: targetedDomains.reason,
      qualificationDebug: targetedDomains.qualificationDebug,
      checkedAt: targetedDomains.checkedAt,
    })
    .from(targetedDomains)
    .leftJoin(parentDomains, and(eq(targetedDomains.parentId, parentDomains.id), eq(parentDomains.organizationId, currentOrganizationId())))
    .where(and(inOrg(targetedDomains), eq(targetedDomains.campaignId, campaignId)))
    .orderBy(desc(targetedDomains.checkedAt));
}

/**
 * Delete one campaign, its jobs, its targeted domains, and parent rows pointed
 * to by those campaign domains. Parent rows are included through parent_id so
 * campaign cleanup removes both child and discovered parent domains.
 */
export async function deleteCampaign(campaignId: string) {
  const organizationId = currentOrganizationId();
  // qualification_jobs inherit their scope from the campaign: prove it is
  // this organization's before touching either.
  if (!(await getCampaign(campaignId))) {
    return { campaignDeleted: false, jobsDeleted: 0, domainsDeleted: 0 };
  }
  const deletedDomains = await db.execute(sql`
    WITH RECURSIVE domains_to_delete AS (
      SELECT id
      FROM ${targetedDomains}
      WHERE ${targetedDomains.campaignId} = ${campaignId}
        AND ${targetedDomains.organizationId} = ${organizationId}

      UNION

      SELECT parent.id
      FROM ${targetedDomains} parent
      JOIN domains_to_delete child ON parent.id = (
        SELECT ${targetedDomains.parentId}
        FROM ${targetedDomains}
        WHERE ${targetedDomains.id} = child.id
      )
      WHERE parent.id IS NOT NULL
        AND parent.organization_id = ${organizationId}
    ),
    deleted AS (
      DELETE FROM ${targetedDomains}
      WHERE id IN (SELECT id FROM domains_to_delete)
        AND organization_id = ${organizationId}
      RETURNING id
    )
    SELECT count(*)::int AS count FROM deleted
  `);

  const deletedJobs = await db
    .delete(qualificationJobs)
    .where(eq(qualificationJobs.campaignId, campaignId))
    .returning({ id: qualificationJobs.id });

  const deletedCampaign = await db
    .delete(campaigns)
    .where(and(inOrg(campaigns), eq(campaigns.id, campaignId)))
    .returning({ id: campaigns.id });

  return {
    campaignDeleted: deletedCampaign.length > 0,
    jobsDeleted: deletedJobs.length,
    domainsDeleted: Number(deletedDomains[0]?.count ?? 0),
  };
}

/**
 * Assemble the campaign output: the Apollo link of all qualified domains.
 * Persists the link onto the campaign.
 */
export async function assembleApolloLink(campaignId: string): Promise<string> {
  const [campaign] = await db
    .select()
    .from(campaigns)
    .where(and(inOrg(campaigns), eq(campaigns.id, campaignId)))
    .limit(1);
  if (!campaign) throw new Error(`campaign ${campaignId} not found`);

  const rows = await db
    .select({ domain: targetedDomains.domain })
    .from(targetedDomains)
    .where(
      and(inOrg(targetedDomains), eq(targetedDomains.campaignId, campaignId), eq(targetedDomains.status, "qualified")),
    );

  const url = buildApolloPeopleSearchUrl({
    domains: rows.map((r) => r.domain),
    titles: campaign.jobTitles ?? [],
  });

  await db.update(campaigns).set({ apolloLink: url }).where(and(inOrg(campaigns), eq(campaigns.id, campaignId)));
  return url;
}
