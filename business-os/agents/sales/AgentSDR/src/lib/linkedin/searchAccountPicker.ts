import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { getSearchUsage } from "@/lib/linkedin/searchLeadLimit";
import { linkedInAccounts } from "@/lib/linkedin/schema";
import { inOrg } from "@/lib/tenancy/scope";
import type { LinkedInAccount } from "@/lib/linkedin/schema";

/**
 * Pure, synchronous selection over an in-memory account list — no DB access. The search
 * queue job keeps its own local snapshot (updated as it spends quota) and calls this
 * directly so a worker can claim an account in the same tick it's picked, with no `await`
 * in between where a concurrent worker could pick the very same one.
 *
 * `minRemaining` restricts to accounts whose own remaining quota can cover that many more
 * leads outright — used to move a search to an account that can actually finish it instead
 * of grinding partway on one that can't.
 *
 * `preferredOrder` is a list of account ids, most-preferred first: the order the user
 * arranged for this search. Accounts in it are used up in that order before any account
 * outside it, and ties (or an absent order) fall back to least-used-today. There is no
 * built-in preference — a name hardcoded here would silently outrank the user's choice.
 */
export const selectBestAccount = (
  accounts: LinkedInAccount[],
  excludeIds: Set<string> | string[] = [],
  minRemaining = 0,
  preferredOrder: string[] = [],
  /** Leads per account per day: the organization's searchLeadsPerDay rule. */
  dailyLimit?: number
): LinkedInAccount | null => {
  const exclude = excludeIds instanceof Set ? excludeIds : new Set(excludeIds);
  const rankById = new Map(preferredOrder.map((id, i) => [id, i]));
  const rankOf = (a: LinkedInAccount) => rankById.get(a.id) ?? preferredOrder.length;

  const candidates = accounts
    .filter((a) => a.status === "CONNECTED" && !exclude.has(a.id))
    .filter((a) => getSearchUsage(a.searchLeadsToday, dailyLimit).remaining >= minRemaining);

  candidates.sort((a, b) => {
    const rankDiff = rankOf(a) - rankOf(b);
    if (rankDiff !== 0) return rankDiff;
    return a.searchLeadsToday - b.searchLeadsToday;
  });

  return candidates[0] ?? null;
};

/** DB-backed convenience wrapper for one-off lookups outside the search queue job's loop. */
export const pickAvailableSearchAccount = async (excludeIds: string[] = []): Promise<LinkedInAccount | null> => {
  const accounts = await db
    .select()
    .from(linkedInAccounts)
    .where(and(inOrg(linkedInAccounts), eq(linkedInAccounts.status, "CONNECTED")));
  return selectBestAccount(accounts, excludeIds);
};
