/**
 * Let a workspace tell the CRM's AI how to write and how to classify.
 *
 * Run with: bun run scripts/add-crm-ai-instructions.ts
 *
 * Two free-text columns on the pipeline's settings row, edited on
 * CRM Settings → AI instructions:
 *
 *   draft_instructions           — appended to the system prompt of every
 *                                  reply / follow-up draft (src/lib/crm/ai/draft.ts)
 *   classification_instructions  — appended to the system prompt of every
 *                                  reply and call classification (src/lib/crm/ai/classify.ts)
 *
 * NULL means "no extra instructions" — the prompts are then exactly what they
 * were before this column existed. The length cap mirrors the API's.
 *
 * Bun loads .env.local automatically.
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
    await client.query("BEGIN");
    await client.query(`
      ALTER TABLE crm_settings
        ADD COLUMN IF NOT EXISTS draft_instructions text,
        ADD COLUMN IF NOT EXISTS classification_instructions text
    `);
    await client.query(`
      DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'crm_settings_instructions_len_chk') THEN
          ALTER TABLE crm_settings ADD CONSTRAINT crm_settings_instructions_len_chk CHECK (
            coalesce(length(draft_instructions), 0) <= 8000
            AND coalesce(length(classification_instructions), 0) <= 8000
          );
        END IF;
      END $$
    `);
    await client.query("COMMIT");

    const { rows } = await client.query(`
      SELECT pipeline_id,
             length(draft_instructions) AS draft_chars,
             length(classification_instructions) AS classification_chars
      FROM crm_settings
    `);
    console.table(rows);
  } catch (error) {
    await client.query("ROLLBACK").catch(() => undefined);
    throw error;
  } finally {
    await client.end();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
