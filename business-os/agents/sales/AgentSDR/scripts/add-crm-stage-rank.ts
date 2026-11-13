/**
 * Adds crm_subcategories.stage_rank — where a subcategory sits in the sales
 * funnel — and ranks the seeded taxonomy.
 *
 * Run with:  bun run scripts/add-crm-stage-rank.ts
 *
 * The AI may only move a record forward: once a record sits on a ranked
 * stage, a classification that would land it on a lower-ranked or unranked
 * subcategory is held for human review instead of being applied
 * (classificationApplicationDecision, "protected_stage"). A person can still
 * move a record anywhere. Equal ranks are lateral moves and stay automatic,
 * which is why Meeting No Show shares Meeting Requested's rank.
 *
 * NULL means "not a funnel stage" (Out of Office, Left Company, the Not
 * Interested outcomes). Ranks are editable in CRM settings; this only fills
 * rows that have none, so re-running never overwrites a rank someone set.
 */
import { Client } from "pg";

/** Subcategory key → rank. Keys are the slugs of the seeded names. */
const DEFAULT_STAGE_RANKS: Readonly<Record<string, number>> = {
  information_requested: 1,
  case_study: 1,
  demo_requested: 1,
  meeting_requested: 2,
  meeting_no_show: 2,
  meeting_done: 3,
  trial_requested: 4,
  trial_user: 5,
  customer: 6,
};

const DDL = `
ALTER TABLE crm_subcategories ADD COLUMN IF NOT EXISTS stage_rank integer;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'crm_subcategories_stage_rank_chk'
  ) THEN
    ALTER TABLE crm_subcategories
      ADD CONSTRAINT crm_subcategories_stage_rank_chk
      CHECK (stage_rank IS NULL OR stage_rank >= 1);
  END IF;
END $$;
`;

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
    await client.query(DDL);
    for (const [key, rank] of Object.entries(DEFAULT_STAGE_RANKS)) {
      await client.query(
        `UPDATE crm_subcategories SET stage_rank = $2, updated_at = now()
          WHERE key = $1 AND stage_rank IS NULL`,
        [key, rank],
      );
    }
    await client.query("COMMIT");
    const { rows } = await client.query(
      `SELECT category_key, key, name, stage_rank FROM crm_subcategories
        ORDER BY stage_rank NULLS LAST, category_key, sort_order`,
    );
    console.table(rows);
  } catch (error) {
    await client.query("ROLLBACK").catch(() => undefined);
    throw error;
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
