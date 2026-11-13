/**
 * Finalizes unified People constraints after cleanup and person backfill.
 *
 * Check only: bun run scripts/finalize-lead-tables.ts
 * Apply:      bun run scripts/finalize-lead-tables.ts --apply
 *
 * With no --apply this performs data/catalog checks and prints every blocker.
 * It never repairs data and never drops an invalid index automatically.
 */
import { Client } from "pg";

type Blocker = { check: string; count: number };

const UNIQUE_INDEXES = [
  {
    name: "people_email_uq",
    sql: `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS people_email_uq
      ON people (lower(email)) WHERE email IS NOT NULL`,
  },
  {
    name: "people_linkedin_url_uq",
    sql: `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS people_linkedin_url_uq
      ON people (linkedin_url) WHERE linkedin_url IS NOT NULL`,
  },
  {
    name: "outreach_leads_person_campaign_uq",
    sql: `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS outreach_leads_person_campaign_uq
      ON outreach_leads (person_id, campaign_id)`,
  },
  {
    name: "outreach_mailbox_queue_lead_uq",
    sql: `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS outreach_mailbox_queue_lead_uq
      ON outreach_mailbox_queue (lead_id)`,
  },
  {
    name: "outreach_emails_lead_step_uq",
    sql: `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS outreach_emails_lead_step_uq
      ON outreach_emails (lead_id, step_number)`,
  },
  {
    name: "crm_messages_provider_id_uq",
    sql: `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS crm_messages_provider_id_uq
      ON crm_messages (smartlead_message_id) WHERE smartlead_message_id IS NOT NULL`,
  },
  {
    name: "Lead_personId_campaignId_key",
    sql: `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "Lead_personId_campaignId_key"
      ON "Lead" ("personId", "campaignId")`,
  },
  {
    name: "Lead_sourceLinkedinIdentifier_campaignId_key",
    sql: `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "Lead_sourceLinkedinIdentifier_campaignId_key"
      ON "Lead" ("sourceLinkedinIdentifier", coalesce("sourceLinkedinApi", ''), "campaignId")
      WHERE "sourceLinkedinIdentifier" IS NOT NULL`,
  },
  {
    name: "Message_automated_lead_type_uq",
    sql: `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "Message_automated_lead_type_uq"
      ON "Message" ("leadId", "type")
      WHERE "leadId" IS NOT NULL AND "duplicateOfMessageId" IS NULL
        AND "type" IN ('INVITATION', 'ACCEPTANCE', 'FOLLOW_UP_1', 'FOLLOW_UP_2', 'FOLLOW_UP_3')`,
  },
] as const;

const BLOCKER_QUERIES = [
  ["people duplicate emails", `
    SELECT count(*)::int AS count FROM (
      SELECT lower(email) FROM people WHERE email IS NOT NULL
      GROUP BY lower(email) HAVING count(*) > 1
    ) conflicts
  `],
  ["people duplicate LinkedIn identities", `
    SELECT count(*)::int AS count FROM (
      SELECT linkedin_url FROM people WHERE linkedin_url IS NOT NULL
      GROUP BY linkedin_url HAVING count(*) > 1
    ) conflicts
  `],
  ["Email leads missing person", `SELECT count(*)::int AS count FROM outreach_leads WHERE person_id IS NULL`],
  ["LinkedIn leads missing person", `SELECT count(*)::int AS count FROM "Lead" WHERE "personId" IS NULL`],
  ["orphaned Email person references", `
    SELECT count(*)::int AS count FROM outreach_leads l
    LEFT JOIN people p ON p.id = l.person_id
    WHERE l.person_id IS NOT NULL AND p.id IS NULL
  `],
  ["orphaned LinkedIn person references", `
    SELECT count(*)::int AS count FROM "Lead" l
    LEFT JOIN people p ON p.id = l."personId"
    WHERE l."personId" IS NOT NULL AND p.id IS NULL
  `],
  ["duplicate Email campaign memberships", `
    SELECT count(*)::int AS count FROM (
      SELECT person_id, campaign_id FROM outreach_leads
      WHERE person_id IS NOT NULL GROUP BY person_id, campaign_id HAVING count(*) > 1
    ) conflicts
  `],
  ["duplicate Email queue memberships", `
    SELECT count(*)::int AS count FROM (
      SELECT lead_id FROM outreach_mailbox_queue GROUP BY lead_id HAVING count(*) > 1
    ) conflicts
  `],
  ["duplicate Email step attempts", `
    SELECT count(*)::int AS count FROM (
      SELECT lead_id, step_number FROM outreach_emails
      GROUP BY lead_id, step_number HAVING count(*) > 1
    ) conflicts
  `],
  ["duplicate inbound Email provider IDs", `
    SELECT count(*)::int AS count FROM (
      SELECT smartlead_message_id FROM crm_messages
      WHERE smartlead_message_id IS NOT NULL
      GROUP BY smartlead_message_id HAVING count(*) > 1
    ) conflicts
  `],
  ["duplicate LinkedIn campaign memberships", `
    SELECT count(*)::int AS count FROM (
      SELECT "personId", "campaignId" FROM "Lead"
      WHERE "personId" IS NOT NULL GROUP BY "personId", "campaignId" HAVING count(*) > 1
    ) conflicts
  `],
  ["duplicate unresolved LinkedIn campaign identifiers", `
    SELECT count(*)::int AS count FROM (
      SELECT "sourceLinkedinIdentifier", coalesce("sourceLinkedinApi", ''), "campaignId" FROM "Lead"
      WHERE "sourceLinkedinIdentifier" IS NOT NULL
      GROUP BY "sourceLinkedinIdentifier", coalesce("sourceLinkedinApi", ''), "campaignId" HAVING count(*) > 1
    ) conflicts
  `],
  ["duplicate automated LinkedIn message groups", `
    SELECT count(*)::int AS count FROM (
      SELECT "leadId", "type" FROM "Message"
      WHERE "leadId" IS NOT NULL AND "duplicateOfMessageId" IS NULL
        AND "type" IN ('INVITATION', 'ACCEPTANCE', 'FOLLOW_UP_1', 'FOLLOW_UP_2', 'FOLLOW_UP_3')
      GROUP BY "leadId", "type" HAVING count(*) > 1
    ) conflicts
  `],
  ["orphaned duplicate-message references", `
    SELECT count(*)::int AS count
    FROM "Message" duplicate
    LEFT JOIN "Message" canonical ON canonical.id = duplicate."duplicateOfMessageId"
    WHERE duplicate."duplicateOfMessageId" IS NOT NULL AND canonical.id IS NULL
  `],
  ["chained duplicate-message references", `
    SELECT count(*)::int AS count
    FROM "Message" duplicate
    JOIN "Message" canonical ON canonical.id = duplicate."duplicateOfMessageId"
    WHERE canonical."duplicateOfMessageId" IS NOT NULL
  `],
  ["ambiguous actionable provider/account ownership", `
    SELECT count(*)::int AS count FROM (
      SELECT "providerId", "linkedinAccountId" FROM "Lead"
      WHERE "providerId" IS NOT NULL AND "linkedinAccountId" IS NOT NULL
        AND "supersededByLeadId" IS NULL
        AND status NOT IN ('COMPLETED', 'REPLIED', 'FAILED', 'CANCELLED')
      GROUP BY "providerId", "linkedinAccountId" HAVING count(*) > 1
    ) conflicts
  `],
] as const;

async function assertPrepared(client: Client) {
  const { rows } = await client.query<{ name: string }>(`
    SELECT table_name || '.' || column_name AS name
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND (table_name, column_name) IN (
        ('outreach_leads', 'person_id'),
        ('Lead', 'personId'),
        ('Lead', 'sourceLinkedinIdentifier'),
        ('Lead', 'sourceLinkedinApi'),
        ('Lead', 'resolveRetryCount'),
        ('Lead', 'resolveNextAttemptAt'),
        ('Lead', 'resolveLastError'),
        ('Lead', 'supersededByLeadId'),
        ('Message', 'duplicateOfMessageId'),
        ('WebhookEvent', 'providerEventKey'),
        ('WebhookEvent', 'processingAttempt'),
        ('WebhookEvent', 'processingStartedAt'),
        ('WebhookEvent', 'nextAttemptAt'),
        ('WebhookEvent', 'processedAt')
      )
  `);
  const present = new Set(rows.map((row) => row.name));
  const required = [
    "outreach_leads.person_id",
    "Lead.personId",
    "Lead.sourceLinkedinIdentifier",
    "Lead.sourceLinkedinApi",
    "Lead.resolveRetryCount",
    "Lead.resolveNextAttemptAt",
    "Lead.resolveLastError",
    "Lead.supersededByLeadId",
    "Message.duplicateOfMessageId",
    "WebhookEvent.providerEventKey",
    "WebhookEvent.processingAttempt",
    "WebhookEvent.processingStartedAt",
    "WebhookEvent.nextAttemptAt",
    "WebhookEvent.processedAt",
  ];
  const missing = required.filter((name) => !present.has(name));
  if (missing.length) throw new Error(`Schema preparation is incomplete: missing ${missing.join(", ")}`);
}

async function findBlockers(client: Client): Promise<Blocker[]> {
  const blockers: Blocker[] = [];
  for (const [check, sql] of BLOCKER_QUERIES) {
    const { rows } = await client.query<{ count: number }>(sql);
    const count = Number(rows[0]?.count ?? 0);
    if (count > 0) blockers.push({ check, count });
  }
  return blockers;
}

async function findInvalidIndexes(client: Client) {
  const names = UNIQUE_INDEXES.map((index) => index.name);
  const { rows } = await client.query<{ name: string }>(`
    SELECT c.relname AS name
    FROM pg_index i
    JOIN pg_class c ON c.oid = i.indexrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = ANY($1::text[])
      AND (NOT i.indisvalid OR NOT i.indisready)
  `, [names]);
  return rows.map((row) => row.name);
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const apply = process.argv.includes("--apply");
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
  });
  await client.connect();
  try {
    await client.query("SET lock_timeout = '5s'");
    await client.query("SET statement_timeout = '2min'");
    if (!apply) await client.query("SET default_transaction_read_only = on");

    await assertPrepared(client);
    const blockers = await findBlockers(client);
    const invalidIndexes = await findInvalidIndexes(client);
    console.log(JSON.stringify({ mode: apply ? "apply" : "check-only", blockers, invalidIndexes }, null, 2));
    if (blockers.length) throw new Error("Finalization blocked by legacy data. Resolve every reported group first.");
    if (invalidIndexes.length) {
      throw new Error(
        `Finalization blocked by invalid indexes: ${invalidIndexes.join(", ")}. Inspect and remove only those exact invalid indexes before retrying.`,
      );
    }
    if (!apply) {
      console.log("Checks passed. Re-run with --apply only after migration approval.");
      return;
    }

    // Concurrent index builds must run outside an explicit transaction.
    for (const index of UNIQUE_INDEXES) {
      console.log(`Creating ${index.name}...`);
      await client.query(index.sql);
    }

    await client.query("BEGIN");
    try {
      await client.query("ALTER TABLE outreach_leads VALIDATE CONSTRAINT outreach_leads_person_fk");
      await client.query('ALTER TABLE "Lead" VALIDATE CONSTRAINT "Lead_personId_fkey"');
      await client.query("ALTER TABLE outreach_leads ALTER COLUMN person_id SET NOT NULL");
      await client.query('ALTER TABLE "Lead" ALTER COLUMN "personId" SET NOT NULL');
      await client.query("ALTER TABLE outreach_leads ALTER COLUMN email DROP NOT NULL");
      await client.query('ALTER TABLE "Lead" ALTER COLUMN "linkedinUrl" DROP NOT NULL');
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    }
    console.log("Lead schema finalization complete.");
  } finally {
    await client.end();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
