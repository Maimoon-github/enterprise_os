/**
 * A rep talking through a calling station: adds call_sessions.remote_rep —
 * null for every other call; for a cloud call the rep talks on from their
 * AgentSDR tab, a marker. First { offer, answer } (the tab's WebRTC offer, the
 * station's answer); since the audio relay (29 Oct 2026) `{}`, with nothing to
 * migrate: older rows' SDPs are simply never read. Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-call-session-remote-rep.ts
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
    await client.query(`ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS remote_rep jsonb`);
    console.log("call_sessions.remote_rep ready");
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
