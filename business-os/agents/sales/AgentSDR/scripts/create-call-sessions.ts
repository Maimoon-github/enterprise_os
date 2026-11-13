/**
 * Creates call_sessions — one row per WhatsApp call placed from the app,
 * indexing its recording in R2. Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/create-call-sessions.ts
 *
 * Requires people.phone to exist first (scripts/add-people-phone.ts) only in
 * the sense that the feature needs both; this table does not reference it.
 *
 * Re-runnable: the table, indexes and constraints are all guarded.
 */
import { Client } from "pg";

const SQL = `
CREATE TABLE IF NOT EXISTS call_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id uuid NOT NULL,
  crm_record_id uuid,
  -- E.164, as dialed.
  phone text NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  -- SHA-256 of the per-call bearer token the recorder extension reports
  -- with. The token itself is never stored.
  upload_token_hash text NOT NULL,
  token_expires_at timestamptz NOT NULL,
  started_at timestamptz,
  ended_at timestamptz,
  duration_ms integer,
  -- Object key in the R2 recordings bucket.
  recording_key text,
  recording_bytes integer,
  recording_content_type text,
  error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT call_sessions_person_fk
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE RESTRICT,
  CONSTRAINT call_sessions_crm_record_fk
    FOREIGN KEY (crm_record_id) REFERENCES crm_records(id) ON DELETE SET NULL,
  CONSTRAINT call_sessions_status_chk
    CHECK (status IN ('pending', 'in_progress', 'recorded', 'no_recording', 'failed')),
  CONSTRAINT call_sessions_recording_chk
    CHECK ((status = 'recorded') = (recording_key IS NOT NULL)),
  CONSTRAINT call_sessions_duration_chk
    CHECK (duration_ms IS NULL OR duration_ms >= 0)
);

CREATE INDEX IF NOT EXISTS call_sessions_person_created_idx
  ON call_sessions (person_id, created_at);
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
    const { rows } = await client.query<{ calls: string }>(`SELECT count(*)::text AS calls FROM call_sessions`);
    console.log(`call_sessions ready: ${rows[0].calls} rows`);
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
