/**
 * Turn the CRM's AI instructions into lists of titled blocks.
 *
 * Run with: bun run scripts/crm-ai-instruction-blocks.ts
 *
 * scripts/add-crm-ai-instructions.ts created crm_settings.draft_instructions
 * and .classification_instructions as free text. The settings page now edits
 * them as an accordion of { id, title, content } blocks, so both become jsonb
 * arrays. Any existing text is kept as a single block titled "Instructions".
 * NULL still means "no instructions".
 *
 * Re-running is safe: the conversion only runs while a column is still text.
 *
 * Bun loads .env.local automatically.
 */
import { Client } from "pg";

const COLUMNS = ["draft_instructions", "classification_instructions"] as const;

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
    await client.query("ALTER TABLE crm_settings DROP CONSTRAINT IF EXISTS crm_settings_instructions_len_chk");

    for (const column of COLUMNS) {
      const { rows } = await client.query<{ data_type: string }>(
        `SELECT data_type FROM information_schema.columns
         WHERE table_name = 'crm_settings' AND column_name = $1`,
        [column],
      );
      if (!rows[0]) throw new Error(`crm_settings.${column} is missing — run add-crm-ai-instructions.ts first`);
      if (rows[0].data_type === "jsonb") continue;
      await client.query(`
        ALTER TABLE crm_settings ALTER COLUMN ${column} TYPE jsonb USING (
          CASE WHEN ${column} IS NULL OR btrim(${column}) = '' THEN NULL
          ELSE jsonb_build_array(jsonb_build_object(
            'id', gen_random_uuid()::text,
            'title', 'Instructions',
            'content', btrim(${column})
          )) END
        )
      `);
    }

    await client.query(`
      DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'crm_settings_instructions_shape_chk') THEN
          ALTER TABLE crm_settings ADD CONSTRAINT crm_settings_instructions_shape_chk CHECK (
            (draft_instructions IS NULL OR (jsonb_typeof(draft_instructions) = 'array' AND length(draft_instructions::text) <= 60000))
            AND (classification_instructions IS NULL OR (jsonb_typeof(classification_instructions) = 'array' AND length(classification_instructions::text) <= 60000))
          );
        END IF;
      END $$
    `);
    await client.query("COMMIT");

    const { rows } = await client.query(`
      SELECT pipeline_id,
             jsonb_array_length(draft_instructions) AS draft_blocks,
             jsonb_array_length(classification_instructions) AS classification_blocks
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
