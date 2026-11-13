import { and, count, eq, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { leads } from "@/lib/linkedin/schema";
import { inOrg } from "@/lib/tenancy/scope";

export const statusCountsByCampaignIds = async (
  campaignIds: string[]
): Promise<Record<string, Record<string, number>>> => {
  if (campaignIds.length === 0) return {};

  const groups = await db
    .select({ campaignId: leads.campaignId, status: leads.status, count: count() })
    .from(leads)
    .where(and(inOrg(leads), inArray(leads.campaignId, campaignIds)))
    .groupBy(leads.campaignId, leads.status);

  const result: Record<string, Record<string, number>> = {};
  for (const row of groups) {
    if (!row.campaignId) continue;
    if (!result[row.campaignId]) result[row.campaignId] = {};
    result[row.campaignId][row.status] = row.count;
  }
  return result;
};

export const statusCountsForCampaign = async (campaignId: string) => {
  const groups = await db
    .select({ status: leads.status, count: count() })
    .from(leads)
    .where(and(inOrg(leads), eq(leads.campaignId, campaignId)))
    .groupBy(leads.status);

  const counts: Record<string, number> = {};
  for (const row of groups) {
    counts[row.status] = row.count;
  }
  return counts;
};
