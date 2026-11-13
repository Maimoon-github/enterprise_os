/**
 * Read-only inspection for the unified People schema.
 *
 * Run with: bun run scripts/check-lead-schema.ts
 *
 * This command reads PostgreSQL catalogs only. It never creates, alters,
 * updates, or deletes anything.
 */
import { Client } from "pg";

const REQUIRED_COLUMNS = [
  ["outreach_leads", "person_id"],
  ["Lead", "personId"],
  ["Lead", "sourceLinkedinIdentifier"],
  ["Lead", "sourceLinkedinApi"],
  ["Lead", "resolveRetryCount"],
  ["Lead", "resolveNextAttemptAt"],
  ["Lead", "resolveLastError"],
  ["Lead", "supersededByLeadId"],
  ["Message", "duplicateOfMessageId"],
  ["WebhookEvent", "providerEventKey"],
  ["WebhookEvent", "processingAttempt"],
  ["WebhookEvent", "processingStartedAt"],
  ["WebhookEvent", "nextAttemptAt"],
  ["WebhookEvent", "processedAt"],
] as const;

const PREPARED_INDEXES = [
  "WebhookEvent_providerEventKey_uq",
  "WebhookEvent_retry_idx",
  "people_email_lookup_idx",
  "people_linkedin_lookup_idx",
  "Lead_unresolvedLinkedin_lookup_idx",
  "Message_leadId_idx",
] as const;

const FINAL_INDEXES = [
  "people_email_uq",
  "people_linkedin_url_uq",
  "outreach_leads_person_campaign_uq",
  "outreach_mailbox_queue_lead_uq",
  "outreach_emails_lead_step_uq",
  "crm_messages_provider_id_uq",
  "Lead_personId_campaignId_key",
  "Lead_sourceLinkedinIdentifier_campaignId_key",
  "Message_automated_lead_type_uq",
] as const;

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");

  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
  });
  await client.connect();
  try {
    await client.query("SET default_transaction_read_only = on");
    await client.query("SET statement_timeout = '30s'");

    const { rows: tables } = await client.query<{ table_name: string }>(`
      SELECT table_name
      FROM information_schema.tables
      WHERE table_schema = 'public'
        AND table_name IN ('people', 'companies', 'entity_columns', 'import_runs')
      ORDER BY table_name
    `);
    const { rows: columns } = await client.query<{ table_name: string; column_name: string; is_nullable: string }>(`
      SELECT table_name, column_name, is_nullable
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
      ORDER BY table_name, column_name
    `);
    const { rows: constraints } = await client.query<{ conname: string; validated: boolean }>(`
      SELECT conname, convalidated AS validated
      FROM pg_constraint
      WHERE conname IN ('outreach_leads_person_fk', 'Lead_personId_fkey')
      ORDER BY conname
    `);
    const { rows: indexes } = await client.query<{ name: string; valid: boolean; ready: boolean }>(`
      SELECT c.relname AS name, i.indisvalid AS valid, i.indisready AS ready
      FROM pg_index i
      JOIN pg_class c ON c.oid = i.indexrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = 'public'
        AND c.relname = ANY($1::text[])
      ORDER BY c.relname
    `, [[...PREPARED_INDEXES, ...FINAL_INDEXES]]);

    const tableSet = new Set(tables.map((row) => row.table_name));
    const columnMap = new Map(columns.map((row) => [`${row.table_name}.${row.column_name}`, row]));
    const indexMap = new Map(indexes.map((row) => [row.name, row]));
    const missingTables = ["people", "companies", "entity_columns", "import_runs"].filter((name) => !tableSet.has(name));
    const missingColumns = REQUIRED_COLUMNS
      .map(([table, column]) => `${table}.${column}`)
      .filter((name) => !columnMap.has(name));
    const missingPreparedIndexes = PREPARED_INDEXES.filter((name) => !indexMap.has(name));
    const missingFinalIndexes = FINAL_INDEXES.filter((name) => !indexMap.has(name));
    const invalidFinalIndexes = indexes.filter((row) => !row.valid || !row.ready).map((row) => row.name);
    const finalized = missingFinalIndexes.length === 0
      && invalidFinalIndexes.length === 0
      && columnMap.get("outreach_leads.person_id")?.is_nullable === "NO"
      && columnMap.get("Lead.personId")?.is_nullable === "NO"
      && constraints.length === 2
      && constraints.every((row) => row.validated);

    console.log(JSON.stringify({
      mode: "read-only",
      prepared: missingTables.length === 0 && missingColumns.length === 0 && missingPreparedIndexes.length === 0,
      finalized,
      missingTables,
      missingColumns,
      missingPreparedIndexes,
      constraints,
      missingFinalIndexes,
      invalidFinalIndexes,
      personIdNullability: {
        outreachLeads: columnMap.get("outreach_leads.person_id")?.is_nullable ?? "MISSING",
        linkedinLeads: columnMap.get("Lead.personId")?.is_nullable ?? "MISSING",
      },
    }, null, 2));

    if (missingTables.length || missingColumns.length || missingPreparedIndexes.length || invalidFinalIndexes.length) process.exitCode = 1;
  } finally {
    await client.end();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
