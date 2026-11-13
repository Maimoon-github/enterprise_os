import {
  pgTable,
  uuid,
  text,
  integer,
  numeric,
  boolean,
  jsonb,
  timestamp,
  index,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import type { QualificationDebugTrace } from "./types";
import { organizations } from "@/lib/auth/schema";

/** A targeting campaign: a set of filters (or a manual list) + a lead target. */
export const campaigns = pgTable("campaigns", {
  organizationId: uuid("organization_id")
    .notNull()
    .references(() => organizations.id),
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  // "filters" | "manual"
  inputMode: text("input_mode").notNull(),
  // snapshot of getDomains filters; null for manual campaigns
  filters: jsonb("filters"),
  jobTitles: text("job_titles").array(),
  // "leads" (stop once accumulatedLeadCount reaches targetLeadCount) |
  // "domains" (stop once targetDomainCount domains have been qualified)
  targetMode: text("target_mode").notNull().default("leads"),
  targetLeadCount: integer("target_lead_count").notNull().default(3000),
  targetDomainCount: integer("target_domain_count"),
  accumulatedLeadCount: integer("accumulated_lead_count").notNull().default(0),
  apolloLink: text("apollo_link"),
  // "building" | "ready" | "paused" | "done"
  status: text("status").notNull().default("building"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
},
  (t) => [index("campaigns_organization_idx").on(t.organizationId)],
);

/**
 * Global registry of every domain we have touched. Doubles as the per-domain
 * result cache and the do-not-target list. The unique constraint on `domain`
 * is the hard guarantee a domain (incl. a discovered parent) is targeted at
 * most once, ever.
 */
export const targetedDomains = pgTable("targeted_domains", {
  organizationId: uuid("organization_id")
    .notNull()
    .references(() => organizations.id),
  id: uuid("id").primaryKey().defaultRandom(),
  domain: text("domain").notNull(),
  campaignId: uuid("campaign_id").references(() => campaigns.id),
  // "qualified" | "not_live" | "no_ads" | "apollo_no_data" | "apollo_has_data" | "pending"
  status: text("status").notNull().default("pending"),
  // True for rows created because AI resolved them as a parent company.
  isParentCompany: boolean("is_parent_company").notNull().default(false),
  isLive: boolean("is_live"),
  // Apollo total_entries with no email filter — tells us if Apollo has any data at all.
  allLeadCount: integer("all_lead_count"),
  // Apollo total_entries filtered to verified-email people only.
  verifiedEmployeeCount: integer("verified_employee_count"),
  // Annual revenue (from clean_domains.annual_sales). Parent-company rows
  // inherit the revenue of the child domain that discovered them.
  revenue: numeric("revenue"),
  // FK to this domain's parent row in the same table (self-referential).
  parentId: uuid("parent_id"),
  // Denormalised parent domain string for display without a join.
  parentDomain: text("parent_domain"),
  // True when a human must research this domain's parent company.
  parentPending: boolean("parent_pending").notNull().default(false),
  reason: text("reason"),
  qualificationDebug: jsonb("qualification_debug").$type<QualificationDebugTrace | null>(),
  checkedAt: timestamp("checked_at", { withTimezone: true }).defaultNow(),
},
  (t) => [
    index("targeted_domains_organization_idx").on(t.organizationId),
    uniqueIndex("targeted_domains_org_domain_uq").on(t.organizationId, t.domain),
  ],
);

/** A single batch processing run for a campaign (the "Job ID"). */
export const qualificationJobs = pgTable("qualification_jobs", {
  id: uuid("id").primaryKey().defaultRandom(),
  campaignId: uuid("campaign_id")
    .notNull()
    .references(() => campaigns.id),
  // "running" | "cancel_requested" | "cancelled" | "success" | "failed"
  status: text("status").notNull().default("running"),
  requestedLimit: integer("requested_limit"),
  currentDomain: text("current_domain"),
  domainsProcessed: integer("domains_processed").notNull().default(0),
  domainsQualified: integer("domains_qualified").notNull().default(0),
  lastHeartbeatAt: timestamp("last_heartbeat_at", { withTimezone: true }),
  startedAt: timestamp("started_at", { withTimezone: true }).defaultNow(),
  finishedAt: timestamp("finished_at", { withTimezone: true }),
});
