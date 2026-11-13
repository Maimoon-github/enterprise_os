/**
 * Creates whatsapp_campaigns, whatsapp_campaign_accounts,
 * whatsapp_campaign_leads and whatsapp_campaign_sends — WhatsApp message
 * campaigns. Matches src/lib/whatsapp/schema.ts; see
 * docs/whatsapp-campaigns/plan.md.
 *
 * Run with:  bun run scripts/create-whatsapp-campaign-tables.ts
 *
 * New tables only; nothing existing changes. Re-runnable: every table,
 * index and constraint is guarded.
 */
import { Client } from "pg";

const STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS whatsapp_campaigns (
     organization_id uuid NOT NULL REFERENCES organizations(id),
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     name text NOT NULL,
     description text,
     status text NOT NULL DEFAULT 'paused',
     steps jsonb NOT NULL DEFAULT '[]'::jsonb,
     archived_at timestamptz,
     created_at timestamptz NOT NULL DEFAULT now(),
     updated_at timestamptz NOT NULL DEFAULT now(),
     CONSTRAINT whatsapp_campaigns_status_chk CHECK (status IN ('active', 'paused'))
   )`,
  `CREATE INDEX IF NOT EXISTS whatsapp_campaigns_organization_idx ON whatsapp_campaigns (organization_id)`,
  `CREATE TABLE IF NOT EXISTS whatsapp_campaign_accounts (
     campaign_id uuid NOT NULL,
     account_id uuid NOT NULL,
     created_at timestamptz NOT NULL DEFAULT now(),
     CONSTRAINT whatsapp_campaign_accounts_pk PRIMARY KEY (campaign_id, account_id),
     CONSTRAINT whatsapp_campaign_accounts_campaign_fk FOREIGN KEY (campaign_id) REFERENCES whatsapp_campaigns(id) ON DELETE CASCADE,
     CONSTRAINT whatsapp_campaign_accounts_account_fk FOREIGN KEY (account_id) REFERENCES whatsapp_accounts(id) ON DELETE CASCADE
   )`,
  `CREATE INDEX IF NOT EXISTS whatsapp_campaign_accounts_account_idx ON whatsapp_campaign_accounts (account_id)`,
  `CREATE TABLE IF NOT EXISTS whatsapp_campaign_leads (
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     campaign_id uuid NOT NULL,
     person_id uuid NOT NULL,
     phone text NOT NULL,
     custom_fields jsonb NOT NULL DEFAULT '{}'::jsonb,
     status text NOT NULL DEFAULT 'queued',
     current_step integer NOT NULL DEFAULT 0,
     next_send_at timestamptz,
     account_id uuid,
     attempts integer NOT NULL DEFAULT 0,
     last_error text,
     last_sent_at timestamptz,
     replied_at timestamptz,
     created_at timestamptz NOT NULL DEFAULT now(),
     updated_at timestamptz NOT NULL DEFAULT now(),
     CONSTRAINT whatsapp_campaign_leads_campaign_fk FOREIGN KEY (campaign_id) REFERENCES whatsapp_campaigns(id) ON DELETE CASCADE,
     CONSTRAINT whatsapp_campaign_leads_person_fk FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE,
     CONSTRAINT whatsapp_campaign_leads_account_fk FOREIGN KEY (account_id) REFERENCES whatsapp_accounts(id) ON DELETE SET NULL,
     CONSTRAINT whatsapp_campaign_leads_campaign_person_uq UNIQUE (campaign_id, person_id),
     CONSTRAINT whatsapp_campaign_leads_status_chk CHECK (status IN ('queued', 'in_sequence', 'completed', 'replied', 'stopped', 'failed')),
     CONSTRAINT whatsapp_campaign_leads_step_chk CHECK (current_step >= 0)
   )`,
  `CREATE INDEX IF NOT EXISTS whatsapp_campaign_leads_due_idx ON whatsapp_campaign_leads (status, next_send_at)`,
  `CREATE INDEX IF NOT EXISTS whatsapp_campaign_leads_person_idx ON whatsapp_campaign_leads (person_id)`,
  `CREATE TABLE IF NOT EXISTS whatsapp_campaign_sends (
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     lead_id uuid NOT NULL,
     step integer NOT NULL,
     step_id text,
     status text NOT NULL DEFAULT 'sending',
     account_id uuid,
     whatsapp_message_id uuid,
     body text,
     error text,
     created_at timestamptz NOT NULL DEFAULT now(),
     sent_at timestamptz,
     CONSTRAINT whatsapp_campaign_sends_lead_fk FOREIGN KEY (lead_id) REFERENCES whatsapp_campaign_leads(id) ON DELETE CASCADE,
     CONSTRAINT whatsapp_campaign_sends_account_fk FOREIGN KEY (account_id) REFERENCES whatsapp_accounts(id) ON DELETE SET NULL,
     CONSTRAINT whatsapp_campaign_sends_message_fk FOREIGN KEY (whatsapp_message_id) REFERENCES whatsapp_messages(id) ON DELETE SET NULL,
     CONSTRAINT whatsapp_campaign_sends_lead_step_uq UNIQUE (lead_id, step),
     CONSTRAINT whatsapp_campaign_sends_status_chk CHECK (status IN ('sending', 'sent', 'failed'))
   )`,
];

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
  });
  await client.connect();
  try {
    await client.query("SET lock_timeout = '5s'");
    await client.query("SET statement_timeout = '2min'");
    await client.query("BEGIN");
    for (const statement of STATEMENTS) await client.query(statement);
    await client.query("COMMIT");
    const { rows } = await client.query<{ table_name: string }>(
      `SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'whatsapp\\_campaign%' ORDER BY table_name`,
    );
    console.log(`tables: ${rows.map((row) => row.table_name).join(", ")}`);
  } catch (error) {
    await client.query("ROLLBACK").catch(() => {});
    throw error;
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
