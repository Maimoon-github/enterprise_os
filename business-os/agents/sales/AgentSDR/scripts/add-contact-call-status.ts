/**
 * Adds call_campaign_contacts.call_status and .unanswered_attempts — where
 * calling a lead stands, and how far along the retry schedule they are.
 * Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-contact-call-status.ts
 *
 * Additive on purpose: the database is shared with production, whose code
 * still reads and writes the old `status` column (the outcome a rep marked).
 * That column is left as it is; call_status is backfilled from it once, and
 * from the contact's latest call where the rep never marked anything:
 *
 *   an outcome where the rep spoke to them         → connected
 *   no_answer / busy / not_on_whatsapp / wrong_number → the same
 *   never marked: the latest call recorded          → connected
 *                 ended without a recording          → no_answer
 *                 failed                             → failed
 *                 no call                            → new
 *
 * Re-runnable: the columns and constraints are guarded, and the backfill only
 * touches rows still at the default ('new') whose old status says otherwise
 * or that have a call.
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
    await client.query(
      "ALTER TABLE call_campaign_contacts ADD COLUMN IF NOT EXISTS call_status text NOT NULL DEFAULT 'new'",
    );
    await client.query(
      "ALTER TABLE call_campaign_contacts ADD COLUMN IF NOT EXISTS unanswered_attempts integer NOT NULL DEFAULT 0",
    );

    const backfill = await client.query(`
      UPDATE call_campaign_contacts c
      SET call_status = CASE
            WHEN c.status IN ('interested', 'meeting_booked', 'callback', 'send_details', 'not_interested', 'do_not_call')
              THEN 'connected'
            WHEN c.status IN ('no_answer', 'busy', 'not_on_whatsapp', 'wrong_number') THEN c.status
            WHEN latest.status = 'recorded' THEN 'connected'
            WHEN latest.status = 'no_recording' THEN 'no_answer'
            WHEN latest.status = 'failed' THEN 'failed'
            ELSE 'new'
          END,
          unanswered_attempts = CASE
            WHEN c.status IN ('no_answer', 'busy') THEN 1
            WHEN c.status = 'new' AND latest.status = 'no_recording' THEN 1
            ELSE 0
          END
      FROM call_campaign_contacts c2
      LEFT JOIN LATERAL (
        SELECT s.status FROM call_sessions s
        WHERE s.campaign_contact_id = c2.id
        ORDER BY s.created_at DESC
        LIMIT 1
      ) latest ON true
      WHERE c.id = c2.id AND c.call_status = 'new' AND (c.status <> 'new' OR latest.status IS NOT NULL)
    `);
    console.log(`backfilled call_status on ${backfill.rowCount} contacts`);

    await client.query(`
      DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'call_campaign_contacts_call_status_chk') THEN
          ALTER TABLE call_campaign_contacts ADD CONSTRAINT call_campaign_contacts_call_status_chk
            CHECK (call_status IN ('new', 'calling', 'no_answer', 'busy', 'connected', 'not_on_whatsapp', 'wrong_number', 'failed'));
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'call_campaign_contacts_unanswered_attempts_chk') THEN
          ALTER TABLE call_campaign_contacts ADD CONSTRAINT call_campaign_contacts_unanswered_attempts_chk
            CHECK (unanswered_attempts >= 0);
        END IF;
      END $$
    `);
    await client.query("COMMIT");

    const { rows } = await client.query<{ call_status: string; n: string }>(
      "SELECT call_status, count(*)::text AS n FROM call_campaign_contacts GROUP BY call_status ORDER BY call_status",
    );
    for (const row of rows) console.log(`  ${row.call_status}: ${row.n}`);
  } catch (error) {
    await client.query("ROLLBACK").catch(() => {});
    throw error;
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
