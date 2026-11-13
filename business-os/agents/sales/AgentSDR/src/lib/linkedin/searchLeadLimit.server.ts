import { and, eq, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { linkedInAccounts } from "./schema";
import { inOrg } from "@/lib/tenancy/scope";
import { getSearchUsage, type SearchUsage } from "./searchLeadLimit";
import { channelRules } from "@/lib/channels/rules.server";

/**
 * Server-only half of the search quota helpers.
 *
 * Kept apart from ./searchLeadLimit so client components (SearchClient,
 * SearchQueueClient, FilterSelect) can import the pure arithmetic without
 * dragging the postgres driver into the browser bundle.
 */
export const incrementSearchLeadsToday = async (
  linkedinId: string,
  count: number
): Promise<SearchUsage> => {
  const [account] = await db
    .update(linkedInAccounts)
    .set({ searchLeadsToday: sql`${linkedInAccounts.searchLeadsToday} + ${count}` })
    .where(and(inOrg(linkedInAccounts), eq(linkedInAccounts.linkedinId, linkedinId)))
    .returning({ searchLeadsToday: linkedInAccounts.searchLeadsToday });

  return getSearchUsage(account.searchLeadsToday, (await channelRules("linkedin")).searchLeadsPerDay);
};
