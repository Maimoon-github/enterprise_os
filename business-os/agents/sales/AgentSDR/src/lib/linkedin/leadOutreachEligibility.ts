import { and, eq, exists, isNotNull, isNull, lt, lte, ne, notExists, notInArray, or, type SQL } from "drizzle-orm";
import { db } from "@/lib/db";
import { campaignAccounts, campaigns, leads } from "@/lib/linkedin/schema";
import { inOrg } from "@/lib/tenancy/scope";
import { MAX_LEAD_RETRIES } from "./inviteRetry";

/**
 * LinkedIn URLs this account has already contacted (resolved or sent to) under
 * ANY campaign. The same account must never reach the same person twice, even
 * across campaigns — this is the exclusion list for that guard.
 */
const alreadyContactedPeopleByAccount = async (linkedinAccountId: string): Promise<string[]> => {
  const rows = await db
    .selectDistinct({ personId: leads.personId })
    .from(leads)
    .where(and(inOrg(leads), eq(leads.linkedinAccountId, linkedinAccountId), ne(leads.status, "PENDING")));
  return rows.flatMap((r) => r.personId ? [r.personId] : []);
};

/**
 * The campaign half of the eligibility rule, shared by both helpers below:
 * the lead has no campaign at all, or its campaign is ACTIVE and either has no
 * account assignments (open to any sender) or explicitly includes this sender.
 */
const campaignEligibility = (linkedinAccountId: string): SQL =>
  or(
    isNull(leads.campaignId),
    exists(
      db
        .select({ one: campaigns.id })
        .from(campaigns)
        .where(
          and(
            eq(campaigns.id, leads.campaignId),
            eq(campaigns.status, "ACTIVE"),
            notExists(
              db
                .select({ one: campaignAccounts.campaignId })
                .from(campaignAccounts)
                .where(eq(campaignAccounts.campaignId, campaigns.id))
            )
          )
        )
    ),
    exists(
      db
        .select({ one: campaigns.id })
        .from(campaigns)
        .where(
          and(
            eq(campaigns.id, leads.campaignId),
            eq(campaigns.status, "ACTIVE"),
            exists(
              db
                .select({ one: campaignAccounts.campaignId })
                .from(campaignAccounts)
                .where(
                  and(
                    eq(campaignAccounts.campaignId, campaigns.id),
                    eq(campaignAccounts.linkedinAccountId, linkedinAccountId)
                  )
                )
            )
          )
        )
    )
  )!;

/** Leads this sender may invite (campaign assignment + active campaign rules). */
export const pendingLeadsSendableByAccount = async (linkedinAccountId: string): Promise<SQL> => {
  const excludedPeople = await alreadyContactedPeopleByAccount(linkedinAccountId);
  return and(
    inOrg(leads),
    eq(leads.status, "PENDING"),
    lt(leads.inviteRetryCount, MAX_LEAD_RETRIES),
    isNotNull(leads.providerId),
    isNotNull(leads.personId),
    isNull(leads.sourceLinkedinIdentifier),
    ...(excludedPeople.length > 0 ? [notInArray(leads.personId, excludedPeople)] : []),
    campaignEligibility(linkedinAccountId)
  )!;
};

/** Leads this sender may resolve before inviting (same campaign rules, not yet resolved). */
export const pendingLeadsResolvableByAccount = async (linkedinAccountId: string): Promise<SQL> => {
  const excludedPeople = await alreadyContactedPeopleByAccount(linkedinAccountId);
  return and(
    inOrg(leads),
    eq(leads.status, "PENDING"),
    lt(leads.resolveRetryCount, MAX_LEAD_RETRIES),
    isNotNull(leads.sourceLinkedinIdentifier),
    or(isNull(leads.resolveNextAttemptAt), lte(leads.resolveNextAttemptAt, new Date())),
    ...(excludedPeople.length > 0 ? [notInArray(leads.personId, excludedPeople)] : []),
    campaignEligibility(linkedinAccountId)
  )!;
};
