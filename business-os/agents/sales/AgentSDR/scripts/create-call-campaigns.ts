/**
 * The Calling section: campaigns, the people in them, follow-up messages,
 * and the outcome and transcript of each call. Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/create-call-campaigns.ts
 *
 * Needs call_sessions first (scripts/create-call-sessions.ts), which this
 * extends with campaign_contact_id, disposition and the transcript columns.
 *
 * Re-runnable: every table, column, index and constraint is guarded.
 */
import { Client } from "pg";

const SQL = `
CREATE TABLE IF NOT EXISTS call_campaigns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  archived_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT call_campaigns_name_chk CHECK (length(btrim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS call_campaign_contacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id uuid NOT NULL,
  person_id uuid NOT NULL,
  -- Which tab: to_call | follow_up | done.
  stage text NOT NULL DEFAULT 'to_call',
  -- The latest call's outcome (CALL_DISPOSITIONS in src/lib/calls/contract.ts), or 'new'.
  status text NOT NULL DEFAULT 'new',
  status_updated_at timestamptz,
  follow_up_at timestamptz,
  notes text,
  call_count integer NOT NULL DEFAULT 0,
  last_called_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT call_campaign_contacts_campaign_fk
    FOREIGN KEY (campaign_id) REFERENCES call_campaigns(id) ON DELETE CASCADE,
  CONSTRAINT call_campaign_contacts_person_fk
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE RESTRICT,
  CONSTRAINT call_campaign_contacts_campaign_person_uq UNIQUE (campaign_id, person_id),
  CONSTRAINT call_campaign_contacts_stage_chk CHECK (stage IN ('to_call', 'follow_up', 'done')),
  CONSTRAINT call_campaign_contacts_call_count_chk CHECK (call_count >= 0)
);

CREATE INDEX IF NOT EXISTS call_campaign_contacts_campaign_stage_idx
  ON call_campaign_contacts (campaign_id, stage);

ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS campaign_contact_id uuid;
ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS disposition text;
ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS transcript_status text NOT NULL DEFAULT 'none';
ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS transcript jsonb;
ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS transcript_error text;
ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS transcribed_at timestamptz;

DO $$ BEGIN
  ALTER TABLE call_sessions ADD CONSTRAINT call_sessions_campaign_contact_fk
    FOREIGN KEY (campaign_contact_id) REFERENCES call_campaign_contacts(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE call_sessions ADD CONSTRAINT call_sessions_transcript_status_chk
    CHECK (transcript_status IN ('none', 'pending', 'done', 'failed'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS call_sessions_campaign_contact_idx
  ON call_sessions (campaign_contact_id);

CREATE TABLE IF NOT EXISTS call_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id uuid NOT NULL,
  campaign_contact_id uuid,
  call_session_id uuid,
  phone text NOT NULL,
  body text NOT NULL,
  -- When the page opened it in WhatsApp; the rep presses Enter themselves.
  opened_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT call_messages_person_fk
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE RESTRICT,
  CONSTRAINT call_messages_campaign_contact_fk
    FOREIGN KEY (campaign_contact_id) REFERENCES call_campaign_contacts(id) ON DELETE CASCADE,
  CONSTRAINT call_messages_call_session_fk
    FOREIGN KEY (call_session_id) REFERENCES call_sessions(id) ON DELETE SET NULL,
  CONSTRAINT call_messages_body_chk CHECK (length(btrim(body)) > 0)
);

CREATE INDEX IF NOT EXISTS call_messages_campaign_contact_idx
  ON call_messages (campaign_contact_id, opened_at);
`;

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
    await client.query(SQL);
    await client.query("COMMIT");
    const { rows } = await client.query<{ campaigns: string; contacts: string }>(
      `SELECT (SELECT count(*) FROM call_campaigns)::text AS campaigns,
              (SELECT count(*) FROM call_campaign_contacts)::text AS contacts`,
    );
    console.log(`calling tables ready: ${rows[0].campaigns} campaigns, ${rows[0].contacts} contacts`);
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
