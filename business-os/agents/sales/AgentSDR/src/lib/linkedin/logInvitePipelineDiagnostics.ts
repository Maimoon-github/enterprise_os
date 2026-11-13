import { and, count, eq, isNotNull, isNull, lt, type SQL } from "drizzle-orm";
import { db } from "@/lib/db";
import { leads } from "@/lib/linkedin/schema";
import { inOrg } from "@/lib/tenancy/scope";
import { MAX_LEAD_RETRIES } from "./inviteRetry";
import {
  pendingLeadsResolvableByAccount,
  pendingLeadsSendableByAccount,
} from "./leadOutreachEligibility";

const countLeads = async (where: SQL | undefined): Promise<number> => {
  const [row] = await db.select({ n: count() }).from(leads).where(and(inOrg(leads), where));
  return row.n;
};

/** Log why sendInvitations found zero candidates for this sender. */
export const logInviteSendDiagnostics = async (
  username: string,
  linkedinAccountId: string
): Promise<void> => {
  const sendableWhere = await pendingLeadsSendableByAccount(linkedinAccountId);
  const [sendable, pendingUnresolved, pendingResolved, failed, requestSent] =
    await Promise.all([
      countLeads(sendableWhere),
      countLeads(
        and(
          eq(leads.status, "PENDING"),
          isNull(leads.providerId),
          lt(leads.inviteRetryCount, MAX_LEAD_RETRIES)
        )
      ),
      countLeads(
        and(
          eq(leads.status, "PENDING"),
          isNotNull(leads.providerId),
          lt(leads.inviteRetryCount, MAX_LEAD_RETRIES)
        )
      ),
      countLeads(eq(leads.status, "FAILED")),
      countLeads(eq(leads.status, "REQUEST_SENT")),
    ]);

  const resolvableForSender = await countLeads(
    await pendingLeadsResolvableByAccount(linkedinAccountId)
  );

  console.log(
    `[sendInvitations] @${username} diagnostics — sendable now: ${sendable}, ` +
      `resolvable for this sender: ${resolvableForSender}, ` +
      `pending unresolved (all): ${pendingUnresolved}, ` +
      `pending resolved (all): ${pendingResolved}, ` +
      `REQUEST_SENT: ${requestSent}, FAILED: ${failed}`
  );
};
