/**
 * Adds call_sessions.recording_offset_ms — where the pick-up is in a call's
 * recording. Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-call-recording-offset.ts
 *
 * The recorder extension (0.11+) records from the moment a call opens the
 * microphone rather than from when it notices the pick-up, so the lead's
 * first words are not lost; the recording starts with some ringing, and
 * players start at this offset. NULL for earlier recordings, which started
 * at the pick-up. Nullable, so adding it touches no existing row.
 *
 * Re-runnable: the column is guarded.
 */
import { Client } from "pg";

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
    await client.query("ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS recording_offset_ms integer");
    const { rows } = await client.query<{ n: string }>(
      `SELECT count(*)::text AS n FROM information_schema.columns
       WHERE table_name = 'call_sessions' AND column_name = 'recording_offset_ms'`,
    );
    console.log(`call_sessions.recording_offset_ms ${rows[0].n === "1" ? "present" : "MISSING"}`);
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
