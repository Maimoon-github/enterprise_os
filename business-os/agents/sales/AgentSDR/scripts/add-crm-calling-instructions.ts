/**
 * The organization's calling instructions for the AI voice agent, edited on
 * Settings → Instructions → Calling beside the reply drafting and
 * classification instructions: crm_settings.calling_instructions (titled
 * blocks; null = the defaults in src/lib/calls/callingInstructions.ts).
 * Matches src/lib/crm/schema.ts.
 *
 * Run with:  bun run scripts/add-crm-calling-instructions.ts
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
    await client.query(`ALTER TABLE crm_settings ADD COLUMN IF NOT EXISTS calling_instructions jsonb`);
    await client.query(`DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'crm_settings_calling_instructions_shape_chk') THEN
        ALTER TABLE crm_settings ADD CONSTRAINT crm_settings_calling_instructions_shape_chk
          CHECK (calling_instructions IS NULL OR (jsonb_typeof(calling_instructions) = 'array' AND length(calling_instructions::text) <= 60000));
      END IF;
    END $$`);
    console.log("crm_settings.calling_instructions ready");
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
