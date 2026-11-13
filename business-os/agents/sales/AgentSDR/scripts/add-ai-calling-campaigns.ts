/**
 * AI calling campaigns (src/lib/calls/aiCampaigns/): calling campaigns whose
 * calls the AI agent places by itself, plus AgentSDR's own WhatsApp messaging
 * through a calling station's WhatsApp Web. Matches src/lib/calls/schema.ts
 * and src/lib/whatsapp/schema.ts.
 *
 *   call_campaigns            run_by and the ai_* settings
 *   call_campaign_stations    the numbers an AI campaign calls from
 *   call_campaign_contacts    ai_* — where each lead stands
 *   call_campaign_step_runs   one row per call placed / message sent (the claim)
 *   calling_stations          per-number calls a day, calling hours, gap, warm-up
 *   whatsapp_accounts         provider / station_id: a station's own number as a messaging account
 *   station_message_jobs      WhatsApp messages for a station's worker to send
 *
 * Run with:  bun run scripts/add-ai-calling-campaigns.ts
 *
 * Additive and re-runnable.
 */
import { Client } from "pg";

const STATEMENTS = [
  // --- call_campaigns -------------------------------------------------------
  `ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS run_by text NOT NULL DEFAULT 'rep'`,
  `ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS ai_goal text NOT NULL DEFAULT 'book_meeting'`,
  `ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS ai_instructions text NOT NULL DEFAULT ''`,
  `ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS ai_agent_name text`,
  `ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS ai_agent_voice text`,
  `ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS ai_steps jsonb NOT NULL DEFAULT '[]'::jsonb`,
  `ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS ai_chase_steps jsonb NOT NULL DEFAULT '[]'::jsonb`,
  `ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS ai_booking_url text`,
  `ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS ai_booking_message text`,
  `ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS ai_max_callbacks integer NOT NULL DEFAULT 2`,
  `ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS ai_launched_at timestamptz`,
  constraint("call_campaigns", "call_campaigns_run_by_chk", `CHECK (run_by IN ('rep', 'ai'))`),
  constraint("call_campaigns", "call_campaigns_ai_goal_chk", `CHECK (ai_goal IN ('book_meeting', 'human_callback', 'either'))`),
  constraint("call_campaigns", "call_campaigns_ai_max_callbacks_chk", `CHECK (ai_max_callbacks BETWEEN 0 AND 3)`),

  // --- calling_stations -----------------------------------------------------
  `ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS calls_per_day integer`,
  `ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS calling_hours jsonb`,
  `ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS next_call_at timestamptz`,
  `ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS automation_started_at timestamptz`,

  // --- call_campaign_stations -----------------------------------------------
  `CREATE TABLE IF NOT EXISTS call_campaign_stations (
     campaign_id uuid NOT NULL,
     station_id uuid NOT NULL,
     created_at timestamptz NOT NULL DEFAULT now(),
     CONSTRAINT call_campaign_stations_pkey PRIMARY KEY (campaign_id, station_id),
     CONSTRAINT call_campaign_stations_campaign_fk FOREIGN KEY (campaign_id) REFERENCES call_campaigns(id) ON DELETE CASCADE,
     CONSTRAINT call_campaign_stations_station_fk FOREIGN KEY (station_id) REFERENCES calling_stations(id) ON DELETE CASCADE
   )`,
  `CREATE INDEX IF NOT EXISTS call_campaign_stations_station_idx ON call_campaign_stations (station_id)`,

  // --- call_campaign_contacts -----------------------------------------------
  `ALTER TABLE call_campaign_contacts ADD COLUMN IF NOT EXISTS ai_status text`,
  `ALTER TABLE call_campaign_contacts ADD COLUMN IF NOT EXISTS ai_step integer NOT NULL DEFAULT 0`,
  `ALTER TABLE call_campaign_contacts ADD COLUMN IF NOT EXISTS ai_next_at timestamptz`,
  `ALTER TABLE call_campaign_contacts ADD COLUMN IF NOT EXISTS ai_station_id uuid`,
  `ALTER TABLE call_campaign_contacts ADD COLUMN IF NOT EXISTS ai_callbacks integer NOT NULL DEFAULT 0`,
  `ALTER TABLE call_campaign_contacts ADD COLUMN IF NOT EXISTS ai_failures integer NOT NULL DEFAULT 0`,
  `ALTER TABLE call_campaign_contacts ADD COLUMN IF NOT EXISTS ai_note text`,
  `ALTER TABLE call_campaign_contacts ADD COLUMN IF NOT EXISTS ai_booked_at timestamptz`,
  constraint(
    "call_campaign_contacts",
    "call_campaign_contacts_ai_station_fk",
    `FOREIGN KEY (ai_station_id) REFERENCES calling_stations(id) ON DELETE SET NULL`,
  ),
  constraint(
    "call_campaign_contacts",
    "call_campaign_contacts_ai_status_chk",
    `CHECK (ai_status IS NULL OR ai_status IN ('queued', 'reaching', 'callback', 'chasing', 'booked', 'handoff', 'not_interested', 'unreached', 'replied', 'stopped', 'failed'))`,
  ),
  `CREATE INDEX IF NOT EXISTS call_campaign_contacts_ai_due_idx ON call_campaign_contacts (ai_status, ai_next_at) WHERE ai_status IS NOT NULL`,

  // --- call_campaign_step_runs ----------------------------------------------
  `CREATE TABLE IF NOT EXISTS call_campaign_step_runs (
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     contact_id uuid NOT NULL,
     step_key text NOT NULL,
     kind text NOT NULL,
     status text NOT NULL DEFAULT 'started',
     station_id uuid,
     call_session_id uuid,
     whatsapp_message_id uuid,
     result text,
     error text,
     created_at timestamptz NOT NULL DEFAULT now(),
     finished_at timestamptz,
     CONSTRAINT call_campaign_step_runs_contact_fk FOREIGN KEY (contact_id) REFERENCES call_campaign_contacts(id) ON DELETE CASCADE,
     CONSTRAINT call_campaign_step_runs_contact_step_uq UNIQUE (contact_id, step_key),
     CONSTRAINT call_campaign_step_runs_kind_chk CHECK (kind IN ('call', 'message')),
     CONSTRAINT call_campaign_step_runs_status_chk CHECK (status IN ('started', 'done', 'failed'))
   )`,
  `CREATE INDEX IF NOT EXISTS call_campaign_step_runs_call_idx ON call_campaign_step_runs (call_session_id)`,
  `CREATE INDEX IF NOT EXISTS call_campaign_step_runs_message_idx ON call_campaign_step_runs (whatsapp_message_id)`,
  `CREATE INDEX IF NOT EXISTS call_campaign_step_runs_open_idx ON call_campaign_step_runs (status) WHERE status = 'started'`,

  // --- whatsapp_accounts: a station's own number ----------------------------
  `ALTER TABLE whatsapp_accounts ADD COLUMN IF NOT EXISTS provider text NOT NULL DEFAULT 'unipile'`,
  `ALTER TABLE whatsapp_accounts ADD COLUMN IF NOT EXISTS station_id uuid`,
  constraint(
    "whatsapp_accounts",
    "whatsapp_accounts_provider_chk",
    `CHECK (provider IN ('unipile', 'station') AND ((provider = 'station') = (station_id IS NOT NULL)))`,
  ),
  `CREATE UNIQUE INDEX IF NOT EXISTS whatsapp_accounts_station_uq ON whatsapp_accounts (station_id) WHERE station_id IS NOT NULL`,

  // --- station_message_jobs -------------------------------------------------
  `CREATE TABLE IF NOT EXISTS station_message_jobs (
     organization_id uuid NOT NULL REFERENCES organizations(id),
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     station_id uuid NOT NULL,
     whatsapp_message_id uuid NOT NULL,
     phone text NOT NULL,
     body text NOT NULL,
     status text NOT NULL DEFAULT 'queued',
     claimed_by text,
     claimed_at timestamptz,
     sent_at timestamptz,
     error text,
     created_at timestamptz NOT NULL DEFAULT now(),
     CONSTRAINT station_message_jobs_message_uq UNIQUE (whatsapp_message_id),
     CONSTRAINT station_message_jobs_station_fk FOREIGN KEY (station_id) REFERENCES calling_stations(id) ON DELETE CASCADE,
     CONSTRAINT station_message_jobs_status_chk CHECK (status IN ('queued', 'claimed', 'sent', 'failed'))
   )`,
  `CREATE INDEX IF NOT EXISTS station_message_jobs_organization_idx ON station_message_jobs (organization_id)`,
  `CREATE INDEX IF NOT EXISTS station_message_jobs_queue_idx ON station_message_jobs (station_id, created_at) WHERE status IN ('queued', 'claimed')`,
];

/** ADD CONSTRAINT has no IF NOT EXISTS: guard it on pg_constraint. */
function constraint(table: string, name: string, definition: string): string {
  return `DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '${name}') THEN
      ALTER TABLE ${table} ADD CONSTRAINT ${name} ${definition};
    END IF;
  END $$`;
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
  });
  await client.connect();
  try {
    await client.query("SET lock_timeout = '5s'");
    await client.query("BEGIN");
    for (const statement of STATEMENTS) await client.query(statement);
    await client.query("COMMIT");
    console.log(`AI calling campaigns: ${STATEMENTS.length} statements applied`);
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
