/**
 * Cloud calling: creates calling_stations (one WhatsApp number whose WhatsApp
 * Web runs in a remote browser) and adds the cloud-call columns to
 * call_sessions. Matches src/lib/calls/schema.ts; see
 * src/lib/calls/stationContract.ts.
 *
 * Run with:  bun run scripts/create-calling-stations.ts
 *
 * Additive only: a new table and nullable / defaulted columns, so code that
 * predates it keeps working. Re-runnable: everything is guarded.
 */
import { Client } from "pg";

const STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS calling_stations (
     organization_id uuid NOT NULL REFERENCES organizations(id),
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     name text NOT NULL,
     phone text NOT NULL,
     launcher text NOT NULL DEFAULT 'gologin_cloud',
     gologin_profile_id text,
     status text NOT NULL DEFAULT 'onboarding',
     link_requested_at timestamptz,
     link_code text,
     link_screenshot text,
     link_updated_at timestamptz,
     worker_id text,
     last_seen_at timestamptz,
     last_call_at timestamptz,
     last_error text,
     created_at timestamptz NOT NULL DEFAULT now(),
     updated_at timestamptz NOT NULL DEFAULT now(),
     CONSTRAINT calling_stations_org_phone_uq UNIQUE (organization_id, phone),
     CONSTRAINT calling_stations_launcher_chk CHECK (launcher IN ('local', 'gologin_sdk', 'gologin_cloud')),
     CONSTRAINT calling_stations_status_chk CHECK (status IN ('onboarding', 'active', 'paused', 'logged_out', 'banned'))
   )`,
  `CREATE INDEX IF NOT EXISTS calling_stations_organization_idx ON calling_stations (organization_id)`,

  `ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'rep'`,
  `ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS station_id uuid`,
  `ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS agent_brief text`,
  `ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS live_phase jsonb`,
  `ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS claimed_at timestamptz`,
  `ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS claimed_by text`,
  `DO $$ BEGIN
     IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'call_sessions_mode_chk') THEN
       ALTER TABLE call_sessions ADD CONSTRAINT call_sessions_mode_chk CHECK (mode IN ('rep', 'agent', 'agent_cloud'));
     END IF;
     IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'call_sessions_station_fk') THEN
       ALTER TABLE call_sessions ADD CONSTRAINT call_sessions_station_fk
         FOREIGN KEY (station_id) REFERENCES calling_stations(id) ON DELETE SET NULL;
     END IF;
   END $$`,
  // The worker's claim: open cloud calls, oldest first.
  `CREATE INDEX IF NOT EXISTS call_sessions_cloud_open_idx ON call_sessions (created_at)
     WHERE mode = 'agent_cloud' AND status IN ('pending', 'in_progress')`,
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
    const { rows } = await client.query<{ column_name: string }>(
      `SELECT column_name FROM information_schema.columns
        WHERE table_name = 'call_sessions' AND column_name IN ('mode', 'station_id', 'agent_brief', 'live_phase', 'claimed_at', 'claimed_by')
        ORDER BY column_name`,
    );
    console.log(`calling_stations ready; call_sessions columns: ${rows.map((row) => row.column_name).join(", ")}`);
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
