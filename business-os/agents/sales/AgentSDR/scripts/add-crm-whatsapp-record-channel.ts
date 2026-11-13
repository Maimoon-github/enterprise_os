/**
 * Lets crm_records.active_channel be 'whatsapp' — a lead worked by phone
 * from WhatsApp Calling, whose due follow-ups then show in Action required.
 * Matches src/lib/crm/schema.ts.
 *
 * Run with:  bun run scripts/add-crm-whatsapp-record-channel.ts
 *
 * Only widens the CHECK, so every existing row and every deployment still
 * writing 'email' / 'linkedin' is unaffected. Conversations, messages and
 * drafts keep their email/LinkedIn-only checks until WhatsApp messaging.
 *
 * Re-runnable: drops the constraint if it exists and adds the wider one, in
 * one transaction.
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
    // The live constraint is crm_records_active_channel_chk (from
    // scripts/create-people-crm-core.ts). The first version of this script
    // widened a differently named one, leaving the original in force; drop
    // that stray and widen the original.
    await client.query("ALTER TABLE crm_records DROP CONSTRAINT IF EXISTS crm_records_channel_chk");
    await client.query("ALTER TABLE crm_records DROP CONSTRAINT IF EXISTS crm_records_active_channel_chk");
    await client.query(
      `ALTER TABLE crm_records ADD CONSTRAINT crm_records_active_channel_chk
         CHECK (active_channel IS NULL OR active_channel IN ('email', 'linkedin', 'whatsapp'))`,
    );
    await client.query("COMMIT");
    const { rows } = await client.query<{ def: string }>(
      "SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint WHERE conrelid = 'crm_records'::regclass AND conname LIKE '%channel%'",
    );
    for (const row of rows) console.log(row.def);
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
