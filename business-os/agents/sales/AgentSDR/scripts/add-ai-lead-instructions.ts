/**
 * AI calling campaigns: a lead's own instructions for its calls, on top of the
 * campaign's (call_campaign_contacts.ai_instructions). Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-ai-lead-instructions.ts
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
    await client.query(`ALTER TABLE call_campaign_contacts ADD COLUMN IF NOT EXISTS ai_instructions text`);
    console.log("call_campaign_contacts.ai_instructions ready");
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
