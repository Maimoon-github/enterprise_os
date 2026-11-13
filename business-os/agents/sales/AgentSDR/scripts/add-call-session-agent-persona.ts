/**
 * AI voice agent: adds call_sessions.agent_name / agent_voice (the persona the
 * call was placed with) and agent_outcome (what the agent's record_outcome tool
 * reported). Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-call-session-agent-persona.ts
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
    await client.query(`ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS agent_name text`);
    await client.query(`ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS agent_voice text`);
    await client.query(`ALTER TABLE call_sessions ADD COLUMN IF NOT EXISTS agent_outcome jsonb`);
    console.log("call_sessions.agent_name, agent_voice, agent_outcome ready");
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
