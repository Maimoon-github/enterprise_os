/**
 * Cloud calling: adds call_sessions.timeline — every timed step of a cloud
 * call (the worker's: claim, browser, WhatsApp; the extension's: dialing,
 * ringing, pick-up, the AI's first audio …), posted by the call worker, so a
 * slow call can be read back step by step. Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-call-session-timeline.ts
 *
 * Additive and re-runnable.
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
    await client.query(`ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS timeline jsonb`);
    console.log("call_sessions.timeline ready");
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
