/**
 * AI calling campaigns choose their CRM Knowledge: call_campaigns.ai_knowledge_ids
 * (crm_knowledge_documents ids; null = the organization's "always include"
 * documents). Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-ai-campaign-knowledge.ts
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
    await client.query(`ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS ai_knowledge_ids uuid[]`);
    console.log("call_campaigns.ai_knowledge_ids ready");
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
