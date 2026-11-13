/**
 * Master Inbox data layer. One query parameterized by `section` powers the
 * Inbox/Sent/Replied/Important/OutOfOffice/PendingApproval views.
 *
 * "Scheduled" is the one exception: it reads from outreach_emails instead,
 * since pending/queued sends live in the outreach schema. Inbox messages only
 * represent mail that was actually sent or received.
 */
import { and, eq, or, ilike, desc, asc, gte, lte, count, sql, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { inboxContacts, inboxMessages, inboxDrafts, inboxContactCcs } from "@/lib/inbox/schema";
import { outreachEmails, outreachLeads, outreachCampaigns, mailboxes } from "@/lib/outreach/schema";
import { people } from "@/lib/leads/schema";
import { crmPipelines, crmRecords, crmSubcategories } from "@/lib/crm/schema";
import type { InboxCrmSummary } from "@/lib/crm/inboxContext";
import { loadInboxCrmSummariesForRecords } from "@/lib/crm/inboxContext.server";
import { loadInboxEmailCrmContext } from "@/lib/inbox/crmContext.server";
import { inOrg } from "@/lib/tenancy/scope";
import { leadsInOrg } from "@/lib/outreach/orgScope";
import { recipientsFromRaw, replyAllCc, type EmailAddress, type MessageRecipients } from "@/lib/email/recipients";

/** Ids of the current organization's inbox contacts — inbox messages, drafts and CCs inherit scope through these. */
function orgContactIds() {
  return db.select({ id: inboxContacts.id }).from(inboxContacts).where(inOrg(inboxContacts));
}

export type InboxSection = "inbox" | "sent" | "replied" | "important" | "outOfOffice" | "pendingApproval";

export type InboxFilters = {
  section: InboxSection;
  q?: string;
  leadIds?: string[];
  campaignIds?: string[];
  /** Mailbox addresses are stored as provider account references. */
  accounts?: string[];
  statusKeys?: string[];
  statusGroups?: string[];
  startDate?: Date;
  endDate?: Date;
  page?: number;
  pageSize?: number;
};

export type InboxMessageRow = {
  id: string;
  leadId: string;
  direction: "inbound" | "outbound";
  subject: string | null;
  bodyText: string | null;
  fromEmail: string | null;
  toEmail: string | null;
  sentAt: Date | null;
  important: boolean;
  openedAt: Date | null;
  leadEmail: string;
  leadFirstName: string | null;
  leadLastName: string | null;
  leadCompany: string | null;
  leadMailbox: string | null;
  leadCampaignId: string | null;
  currentStatusKey: string | null;
  statusLabel: string | null;
  statusGroup: string | null;
  hasDraft: boolean;
  /** CRM sequence position for the contact's record; null when the contact has no CRM record. */
  crm?: InboxCrmSummary | null;
};

function sectionCondition(section: InboxSection) {
  switch (section) {
    case "inbox":
      return eq(inboxMessages.direction, "inbound");
    case "sent":
      return eq(inboxMessages.direction, "outbound");
    case "replied":
      // Received replies, excluding auto-generated OOO responders.
      return and(eq(inboxMessages.direction, "inbound"), sql`${crmSubcategories.key} IS DISTINCT FROM 'out_of_office'`);
    case "important":
      return eq(inboxMessages.important, true);
    case "outOfOffice":
      return and(eq(inboxMessages.direction, "inbound"), eq(crmSubcategories.key, "out_of_office"));
    case "pendingApproval":
      // Handled via EXISTS join below — no direction restriction (a draft
      // replies to whichever inbound message it was generated for).
      return undefined;
  }
}

export async function getMailsBySection(filters: InboxFilters): Promise<{ rows: InboxMessageRow[]; total: number }> {
  const page = Math.max(1, filters.page ?? 1);
  const pageSize = Math.min(100, Math.max(10, filters.pageSize ?? 25));

  const conditions = [inOrg(inboxContacts)];
  const sectionCond = sectionCondition(filters.section);
  if (sectionCond) conditions.push(sectionCond);

  if (filters.section === "pendingApproval") {
    conditions.push(sql`EXISTS (SELECT 1 FROM ${inboxDrafts} WHERE ${inboxDrafts.contactId} = ${inboxContacts.id})`);
  }

  if (filters.q) {
    const like = `%${filters.q}%`;
    conditions.push(
      or(
        ilike(inboxMessages.subject, like),
        ilike(inboxMessages.bodyText, like),
        ilike(inboxContacts.email, like),
        ilike(inboxContacts.firstName, like),
        ilike(inboxContacts.lastName, like),
      )!,
    );
  }
  if (filters.leadIds?.length) conditions.push(sql`${inboxContacts.id} IN ${filters.leadIds}`);
  if (filters.campaignIds?.length) conditions.push(sql`${inboxContacts.campaignId} IN ${filters.campaignIds}`);
  if (filters.accounts?.length) conditions.push(sql`${inboxContacts.mailbox} IN ${filters.accounts}`);
  if (filters.statusKeys?.length) conditions.push(sql`${crmSubcategories.key} IN ${filters.statusKeys}`);
  if (filters.statusGroups?.length) conditions.push(sql`${crmRecords.categoryKey} IN ${filters.statusGroups}`);
  if (filters.startDate) conditions.push(gte(inboxMessages.sentAt, filters.startDate));
  if (filters.endDate) conditions.push(lte(inboxMessages.sentAt, filters.endDate));

  const where = conditions.length > 0 ? and(...conditions) : undefined;

  const draftExists = sql<boolean>`EXISTS (SELECT 1 FROM ${inboxDrafts} WHERE ${inboxDrafts.contactId} = ${inboxContacts.id})`;

  const [pageRows, [{ total }]] = await Promise.all([
    db
      .select({
        id: inboxMessages.id,
        leadId: inboxMessages.contactId,
        direction: inboxMessages.direction,
        subject: inboxMessages.subject,
        bodyText: inboxMessages.bodyText,
        fromEmail: inboxMessages.fromEmail,
        toEmail: inboxMessages.toEmail,
        sentAt: inboxMessages.sentAt,
        important: inboxMessages.important,
        openedAt: inboxMessages.openedAt,
        leadEmail: inboxContacts.email,
        leadFirstName: inboxContacts.firstName,
        leadLastName: inboxContacts.lastName,
        leadCompany: inboxContacts.company,
        leadMailbox: inboxContacts.mailbox,
        leadCampaignId: inboxContacts.campaignId,
        currentStatusKey: crmSubcategories.key,
        statusLabel: crmSubcategories.name,
        statusGroup: crmRecords.categoryKey,
        hasDraft: draftExists,
        crmRecordId: crmRecords.id,
      })
      .from(inboxMessages)
      .innerJoin(inboxContacts, eq(inboxMessages.contactId, inboxContacts.id))
      .leftJoin(people, and(inOrg(people), sql`lower(${people.email}) = lower(${inboxContacts.email})`))
      .leftJoin(crmPipelines, and(inOrg(crmPipelines), eq(crmPipelines.isDefault, true)))
      .leftJoin(crmRecords, and(eq(crmRecords.personId, people.id), eq(crmRecords.pipelineId, crmPipelines.id)))
      .leftJoin(crmSubcategories, eq(crmSubcategories.id, crmRecords.subcategoryId))
      .where(where)
      .orderBy(desc(sql`coalesce(${inboxMessages.sentAt}, ${inboxMessages.createdAt})`))
      .limit(pageSize)
      .offset((page - 1) * pageSize),
    db
      .select({ total: count() })
      .from(inboxMessages)
      .innerJoin(inboxContacts, eq(inboxMessages.contactId, inboxContacts.id))
      .leftJoin(people, and(inOrg(people), sql`lower(${people.email}) = lower(${inboxContacts.email})`))
      .leftJoin(crmPipelines, and(inOrg(crmPipelines), eq(crmPipelines.isDefault, true)))
      .leftJoin(crmRecords, and(eq(crmRecords.personId, people.id), eq(crmRecords.pipelineId, crmPipelines.id)))
      .leftJoin(crmSubcategories, eq(crmSubcategories.id, crmRecords.subcategoryId))
      .where(where),
  ]);

  // One batched CRM read for the page, keyed by the record the rows already joined.
  const crmByRecord = await loadInboxCrmSummariesForRecords(
    pageRows.flatMap((row) => (row.crmRecordId ? [row.crmRecordId] : [])),
  );
  const rows: InboxMessageRow[] = pageRows.map(({ crmRecordId, ...row }) => ({
    ...row,
    crm: crmRecordId ? crmByRecord.get(crmRecordId) ?? null : null,
  }));

  return { rows, total };
}

export type ScheduledEmailRow = {
  id: string;
  leadId: string;
  subject: string | null;
  body: string | null;
  stepNumber: number;
  status: string;
  leadEmail: string;
  leadFirstName: string | null;
  leadLastName: string | null;
  campaignId: string;
  campaignName: string;
  mailboxAddress: string | null;
};

/** Scheduled section: upcoming sequence sends across all active campaigns, not yet sent. */
export async function getScheduledEmails(filters: {
  q?: string;
  campaignIds?: string[];
  page?: number;
  pageSize?: number;
}): Promise<{ rows: ScheduledEmailRow[]; total: number }> {
  const page = Math.max(1, filters.page ?? 1);
  const pageSize = Math.min(100, Math.max(10, filters.pageSize ?? 25));

  const conditions = [leadsInOrg(), inOrg(people), eq(outreachEmails.status, "scheduled")];
  if (filters.q) {
    const like = `%${filters.q}%`;
    conditions.push(or(ilike(outreachEmails.subject, like), ilike(people.email, like))!);
  }
  if (filters.campaignIds?.length) conditions.push(sql`${outreachLeads.campaignId} IN ${filters.campaignIds}`);

  const where = and(...conditions);

  const [rows, [{ total }]] = await Promise.all([
    db
      .select({
        id: outreachEmails.id,
        leadId: outreachEmails.leadId,
        subject: outreachEmails.subject,
        body: outreachEmails.body,
        stepNumber: outreachEmails.stepNumber,
        status: outreachEmails.status,
        leadEmail: sql<string>`coalesce(${people.email}, '')`,
        leadFirstName: sql<string | null>`coalesce(${people.firstName}, ${people.raw}->>'firstName')`,
        leadLastName: sql<string | null>`coalesce(${people.lastName}, ${people.raw}->>'lastName')`,
        campaignId: outreachCampaigns.id,
        campaignName: outreachCampaigns.name,
        mailboxAddress: mailboxes.emailAddress,
      })
      .from(outreachEmails)
      .innerJoin(outreachLeads, eq(outreachEmails.leadId, outreachLeads.id))
      .innerJoin(people, eq(outreachLeads.personId, people.id))
      .innerJoin(outreachCampaigns, eq(outreachLeads.campaignId, outreachCampaigns.id))
      .leftJoin(mailboxes, eq(outreachEmails.mailboxId, mailboxes.id))
      .where(where)
      .orderBy(asc(outreachLeads.nextSendAt))
      .limit(pageSize)
      .offset((page - 1) * pageSize),
    db
      .select({ total: count() })
      .from(outreachEmails)
      .innerJoin(outreachLeads, eq(outreachEmails.leadId, outreachLeads.id))
      .innerJoin(people, eq(outreachLeads.personId, people.id))
      .where(where),
  ]);

  return { rows, total };
}

/** Full thread for one inbox contact, ordered chronologically for the detail pane. */
export async function getThreadForLead(leadId: string) {
  const [lead] = await db.select().from(inboxContacts).where(and(inOrg(inboxContacts), eq(inboxContacts.id, leadId))).limit(1);
  if (!lead) return null;

  const [statusConfig, messages, draft, ccs, crm] = await Promise.all([
    db.select({ label: crmSubcategories.name, statusGroup: crmRecords.categoryKey })
      .from(people)
      .innerJoin(crmPipelines, and(inOrg(crmPipelines), eq(crmPipelines.isDefault, true)))
      .innerJoin(crmRecords, and(eq(crmRecords.personId, people.id), eq(crmRecords.pipelineId, crmPipelines.id)))
      .leftJoin(crmSubcategories, eq(crmSubcategories.id, crmRecords.subcategoryId))
      .where(and(inOrg(people), sql`lower(${people.email}) = lower(${lead.email})`))
      .limit(1)
      .then((rows) => rows[0]?.label ? rows[0] : null),
    db
      .select()
      .from(inboxMessages)
      .where(eq(inboxMessages.contactId, leadId))
      .orderBy(asc(sql`coalesce(${inboxMessages.sentAt}, ${inboxMessages.createdAt})`)),
    db
      .select()
      .from(inboxDrafts)
      .where(eq(inboxDrafts.contactId, leadId))
      .orderBy(desc(inboxDrafts.createdAt))
      .limit(1)
      .then((r) => r[0] ?? null),
    // Other addresses seen CC'd on this lead's thread (e.g. a wrong-POC
    // reply looping in the right person) — surfaced so it's visible who
    // else is on this conversation, not just tracked silently in the DB.
    db.select({ email: inboxContactCcs.email }).from(inboxContactCcs).where(eq(inboxContactCcs.contactId, leadId)),
    // Full CRM strip (classification, sequence step, AI draft) when the
    // contact's thread is a CRM email conversation.
    loadInboxEmailCrmContext(leadId),
  ]);

  // Recipients come from the message's own headers. For inbound mail the
  // to_email column is only our mailbox, so it is a last resort there.
  const threadMessages = messages.map(({ raw, ...message }) => ({
    ...message,
    recipients: recipientsFromRaw(raw, message.toEmail) as MessageRecipients,
  }));
  const latestInbound = [...threadMessages].reverse().find((m) => m.direction === "inbound");
  const replyAll: EmailAddress[] = latestInbound ? replyAllCc(latestInbound, { mailbox: lead.mailbox, lead: lead.email }) : [];
  const seen = new Set<string>();
  const mergedCcs = [...ccs.map((c) => c.email), ...replyAll.map((a) => a.email)].filter((email) => {
    const key = email.trim().toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return { lead, statusConfig, messages: threadMessages, draft, ccs: mergedCcs, replyAllCc: replyAll, crm };
}

/** Sidebar nav counts — same three AgentSDR-app actually computed (Inbox/Important/Scheduled), kept cheap. */
export async function getInboxSidebarCounts() {
  const [[inbox], [important], [scheduled]] = await Promise.all([
    db
      .select({ total: count() })
      .from(inboxMessages)
      .where(and(inArray(inboxMessages.contactId, orgContactIds()), eq(inboxMessages.direction, "inbound"), sql`${inboxMessages.openedAt} IS NULL`)),
    db.select({ total: count() }).from(inboxMessages).where(and(inArray(inboxMessages.contactId, orgContactIds()), eq(inboxMessages.important, true))),
    db.select({ total: count() }).from(outreachEmails)
      .innerJoin(outreachLeads, eq(outreachEmails.leadId, outreachLeads.id))
      .where(and(leadsInOrg(), eq(outreachEmails.status, "scheduled"))),
  ]);
  return { inbox: inbox.total, important: important.total, scheduled: scheduled.total };
}

export async function markMessageOpened(id: string) {
  await db.update(inboxMessages).set({ openedAt: new Date() }).where(and(eq(inboxMessages.id, id), inArray(inboxMessages.contactId, orgContactIds())));
}

export async function toggleMessageImportant(id: string, important: boolean) {
  await db.update(inboxMessages).set({ important }).where(and(eq(inboxMessages.id, id), inArray(inboxMessages.contactId, orgContactIds())));
}

export type InboxLeadOption = { id: string; name: string; subtitle: string | null };

/** Leads matching a search term, for the filter panel's "Leads" picker. */
export async function searchInboxLeads(q: string, limit = 20): Promise<InboxLeadOption[]> {
  const like = `%${q}%`;
  const rows = await db
    .select({
      id: inboxContacts.id,
      firstName: inboxContacts.firstName,
      lastName: inboxContacts.lastName,
      email: inboxContacts.email,
      company: inboxContacts.company,
    })
    .from(inboxContacts)
    .where(and(inOrg(inboxContacts), q ? or(ilike(inboxContacts.email, like), ilike(inboxContacts.firstName, like), ilike(inboxContacts.lastName, like)) : undefined))
    .orderBy(desc(inboxContacts.lastReplyAt))
    .limit(limit);

  return rows.map((r) => ({
    id: r.id,
    name: [r.firstName, r.lastName].filter(Boolean).join(" ") || r.email,
    subtitle: r.company ?? r.email,
  }));
}

/** Distinct mailbox addresses represented in the inbox, for the Accounts picker. */
export async function listInboxAccounts(): Promise<string[]> {
  const rows = await db
    .selectDistinct({ mailbox: inboxContacts.mailbox })
    .from(inboxContacts)
    .where(and(inOrg(inboxContacts), sql`${inboxContacts.mailbox} IS NOT NULL`));
  return rows.map((r) => r.mailbox!).filter(Boolean).sort();
}

export async function listInboxStatuses() {
  return db.select({
    statusKey: crmSubcategories.key,
    label: crmSubcategories.name,
    statusGroup: crmSubcategories.categoryKey,
  }).from(crmSubcategories)
    .innerJoin(crmPipelines, eq(crmPipelines.id, crmSubcategories.pipelineId))
    .where(and(inOrg(crmPipelines), eq(crmPipelines.isDefault, true), eq(crmSubcategories.active, true)))
    .orderBy(asc(crmSubcategories.sortOrder));
}
