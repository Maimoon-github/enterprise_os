/**
 * Adds call_campaigns.status — active or paused, the campaigns list's tabs.
 * Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-call-campaign-status.ts
 *
 * Additive: every existing campaign starts active, and code that does not
 * know the column keeps working.
 *
 * Re-runnable: the column and constraint are guarded.
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
    await client.query("ALTER TABLE call_campaigns ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active'");
    await client.query(`
      DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'call_campaigns_status_chk') THEN
          ALTER TABLE call_campaigns ADD CONSTRAINT call_campaigns_status_chk CHECK (status IN ('active', 'paused'));
        END IF;
      END $$
    `);
    const { rows } = await client.query<{ status: string; n: string }>(
      "SELECT status, count(*)::text AS n FROM call_campaigns GROUP BY status ORDER BY status",
    );
    for (const row of rows) console.log(`  ${row.status}: ${row.n}`);
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
