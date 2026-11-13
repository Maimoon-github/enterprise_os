/**
 * Automatic CRM follow-ups: a sequence can send its follow-up drafts on its
 * own, paced per sending account (src/lib/crm/autoFollowUps.ts).
 *
 * Run with:  bun run scripts/add-crm-auto-follow-ups.ts
 *
 * - crm_sequences.auto_send_follow_ups — the per-sequence switch, off by
 *   default, so nothing sends on its own until someone turns it on.
 * - crm_drafts.auto_send_at — set on a follow-up draft of such a sequence;
 *   the sender picks drafts whose time has passed, oldest first.
 * - crm_send_attempts.actor_type may now be 'system' (the sender), not only
 *   'authenticated_operator'; the per-account gap reads those attempts.
 *
 * Additive and idempotent: re-running changes nothing. Run it before the
 * code that reads these columns is deployed.
 */
import { Client } from "pg";

const DDL = `
ALTER TABLE crm_sequences ADD COLUMN IF NOT EXISTS auto_send_follow_ups boolean NOT NULL DEFAULT false;

ALTER TABLE crm_drafts ADD COLUMN IF NOT EXISTS auto_send_at timestamptz;
CREATE INDEX IF NOT EXISTS crm_drafts_auto_send_idx
  ON crm_drafts (auto_send_at)
  WHERE auto_send_at IS NOT NULL AND status = 'awaiting_review';

ALTER TABLE crm_send_attempts DROP CONSTRAINT IF EXISTS crm_send_attempts_actor_chk;
ALTER TABLE crm_send_attempts
  ADD CONSTRAINT crm_send_attempts_actor_chk
  CHECK (actor_type IN ('authenticated_operator', 'system'));
CREATE INDEX IF NOT EXISTS crm_send_attempts_system_account_idx
  ON crm_send_attempts (account_ref, created_at)
  WHERE actor_type = 'system';
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
    await client.query("COMMIT");
    console.log("Automatic CRM follow-up columns are in place.");
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
