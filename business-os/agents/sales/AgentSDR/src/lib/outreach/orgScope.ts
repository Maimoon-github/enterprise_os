import { inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { mailboxes, outreachCampaigns, outreachLeads } from "./schema";

/**
 * Org filters for the outreach tables that inherit their organization.
 * outreach_leads reaches it through outreach_campaigns; outreach_emails and
 * outreach_mailbox_queue through the lead (or the mailbox). Each helper
 * returns a condition to AND into a query's where clause.
 */

/** Ids of the current organization's campaigns, as a subquery. */
function orgCampaignIds() {
  return db.select({ id: outreachCampaigns.id }).from(outreachCampaigns).where(inOrg(outreachCampaigns));
}

/** Ids of the current organization's mailboxes, as a subquery. */
export function orgMailboxIds() {
  return db.select({ id: mailboxes.id }).from(mailboxes).where(inOrg(mailboxes));
}

/** outreach_leads rows of the current organization. */
export function leadsInOrg() {
  return inArray(outreachLeads.campaignId, orgCampaignIds());
}

/** Ids of the current organization's outreach leads, as a subquery. */
export function orgLeadIds() {
  return db.select({ id: outreachLeads.id }).from(outreachLeads).where(leadsInOrg());
}
