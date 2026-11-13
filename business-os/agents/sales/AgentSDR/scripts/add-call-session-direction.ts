/**
 * Incoming calls: adds call_sessions.direction — 'outbound' (AgentSDR placed
 * the call; every call before this) or 'inbound' (a lead called a calling
 * station and the AI agent answered). Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-call-session-direction.ts
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
    await client.query(`ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS direction text NOT NULL DEFAULT 'outbound'`);
    await client.query(`
      DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'call_sessions_direction_chk') THEN
          ALTER TABLE call_sessions ADD CONSTRAINT call_sessions_direction_chk CHECK (direction IN ('outbound', 'inbound'));
        END IF;
      END $$`);
    console.log("call_sessions.direction ready");
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
