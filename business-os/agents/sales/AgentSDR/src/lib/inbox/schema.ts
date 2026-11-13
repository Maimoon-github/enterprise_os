import {
  boolean,
  jsonb,
  pgTable,
  text,
  timestamp,
  uuid,
  index,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import { organizations } from "@/lib/auth/schema";

/**
 * Master Inbox storage is intentionally independent from the People CRM.
 * Unknown senders can remain visible here without creating CRM records, while
 * known outreach replies are also routed into the canonical CRM workflow.
 */
export const inboxContacts = pgTable("crm_leads", {
  organizationId: uuid("organization_id")
    .notNull()
    .references(() => organizations.id),
  id: uuid("id").primaryKey().defaultRandom(),
  email: text("email").notNull(),
  firstName: text("first_name"),
  lastName: text("last_name"),
  company: text("company"),
  domain: text("domain"),
  campaignId: uuid("campaign_id"),
  mailbox: text("mailbox"),
  lastReplyAt: timestamp("last_reply_at", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
},
  (t) => [
    index("crm_leads_organization_idx").on(t.organizationId),
    uniqueIndex("crm_leads_org_email_uq").on(t.organizationId, t.email),
  ],
);

export const inboxMessages = pgTable("crm_messages", {
  id: uuid("id").primaryKey().defaultRandom(),
  contactId: uuid("lead_id").notNull(),
  direction: text("direction").notNull().$type<"inbound" | "outbound">(),
  providerMessageKey: text("smartlead_message_id"),
  subject: text("subject"),
  bodyText: text("body_text"),
  bodyHtml: text("body_html"),
  fromEmail: text("from_email"),
  toEmail: text("to_email"),
  sentAt: timestamp("sent_at", { withTimezone: true }),
  raw: jsonb("raw"),
  important: boolean("important").notNull().default(false),
  openedAt: timestamp("opened_at", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
});

export type InboundEventStatus = "ok" | "skipped" | "error";

export type InboundEventLogStep = {
  ts: string;
  level: "info" | "warn" | "error";
  message: string;
};

/** Durable provider-delivery audit log shared by Gmail and LinkedIn ingest. */
export const inboundEvents = pgTable("crm_webhook_events", {
  organizationId: uuid("organization_id")
    .notNull()
    .references(() => organizations.id),
  id: uuid("id").primaryKey().defaultRandom(),
  source: text("source").notNull().default("gmail"),
  eventType: text("event_type"),
  title: text("title"),
  status: text("status").notNull().default("ok").$type<InboundEventStatus>(),
  steps: jsonb("steps").notNull().default([]).$type<InboundEventLogStep[]>(),
  payload: jsonb("payload").notNull(),
  processed: boolean("processed").notNull().default(false),
  error: text("error"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
},
  (t) => [index("crm_webhook_events_organization_idx").on(t.organizationId)],
);

export const inboxContactCcs = pgTable("crm_lead_ccs", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: text("email").notNull(),
  contactId: uuid("lead_id").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
});

export const inboxDrafts = pgTable("crm_email_drafts", {
  id: uuid("id").primaryKey().defaultRandom(),
  contactId: uuid("lead_id").notNull(),
  replyForMessageId: uuid("reply_for_message_id"),
  subject: text("subject"),
  bodyHtml: text("body_html").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
});

export const inboxTasks = pgTable("crm_tasks", {
  organizationId: uuid("organization_id")
    .notNull()
    .references(() => organizations.id),
  id: uuid("id").primaryKey().defaultRandom(),
  contactId: uuid("lead_id"),
  name: text("name").notNull(),
  description: text("description"),
  isCompleted: boolean("is_completed").notNull().default(false),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
},
  (t) => [index("crm_tasks_organization_idx").on(t.organizationId)],
);

export const inboxNotes = pgTable("crm_notes", {
  organizationId: uuid("organization_id")
    .notNull()
    .references(() => organizations.id),
  id: uuid("id").primaryKey().defaultRandom(),
  contactId: uuid("lead_id"),
  title: text("title").notNull(),
  description: text("description"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
},
  (t) => [index("crm_notes_organization_idx").on(t.organizationId)],
);
