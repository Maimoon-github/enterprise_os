/**
 * Stop holding AI classifications for human review.
 *
 * Run with: bun run scripts/relax-crm-classification-review.ts
 *
 * The CRM only ever drafts — `human_send_only` is still fixed TRUE, so nothing
 * here lets the system send anything by itself. A wrong category costs a wrong
 * draft that a human declines, which is cheaper than the alternative we had:
 * 101 classifications proposed and never applied, so 61 records sat with no
 * category at all and rendered as "Other".
 *
 * `customer_requires_review` was pinned TRUE by a check constraint and the
 * decision was additionally hardcoded in stateMachine.ts. The constraint is
 * dropped here and the code now reads the column, so the behaviour is a
 * setting again rather than an invariant. Re-enable it any time with:
 *
 *   UPDATE crm_settings SET customer_requires_review = true;
 *
 * Bun loads .env.local automatically.
 */
import { Client } from "pg";

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
  });
  await client.connect();
  try {
    // The invariant becomes a setting. human_send_only keeps its constraint.
    await client.query(
      "ALTER TABLE crm_settings DROP CONSTRAINT IF EXISTS crm_settings_customer_review_chk",
    );

    // Confidence 0 keeps the column meaningful (and the 0..1 check satisfied)
    // while letting every classification through.
    const { rowCount } = await client.query(`
      UPDATE crm_settings
      SET review_other = false,
          customer_requires_review = false,
          auto_apply_confidence = 0,
          updated_at = now()
      WHERE review_other
         OR customer_requires_review
         OR auto_apply_confidence > 0
    `);
    console.log(`crm_settings rows relaxed: ${rowCount}`);

    const { rows } = await client.query(`
      SELECT pipeline_id, auto_apply_confidence, review_other,
             customer_requires_review, human_send_only
      FROM crm_settings
    `);
    console.table(rows);
  } finally {
    await client.end();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
