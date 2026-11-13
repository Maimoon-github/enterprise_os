/**
 * Lets CRM conversations, messages, drafts and identity exceptions carry the
 * 'whatsapp' channel, so WhatsApp replies reach the CRM the way LinkedIn
 * ones do. Matches src/lib/crm/schema.ts. (crm_records.active_channel was
 * widened by scripts/add-crm-whatsapp-record-channel.ts.)
 *
 * Run with:  bun run scripts/add-crm-whatsapp-channel.ts
 *
 * Only widens checks — every existing row and every deployment writing
 * 'email' / 'linkedin' is unaffected — and adds that a WhatsApp draft, like
 * a LinkedIn one, has no subject.
 *
 * Re-runnable: each constraint is dropped if present and re-added, in one
 * transaction.
 */
import { Client } from "pg";

const WIDENED: Array<[table: string, constraint: string]> = [
  ["crm_identity_exceptions", "crm_identity_exceptions_channel_chk"],
  ["crm_conversations", "crm_conversations_channel_chk"],
  ["crm_conversation_messages", "crm_conversation_messages_channel_chk"],
  ["crm_drafts", "crm_drafts_channel_chk"],
];

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
    for (const [table, constraint] of WIDENED) {
      await client.query(`ALTER TABLE ${table} DROP CONSTRAINT IF EXISTS ${constraint}`);
      await client.query(
        `ALTER TABLE ${table} ADD CONSTRAINT ${constraint} CHECK (channel IN ('email', 'linkedin', 'whatsapp'))`,
      );
    }
    await client.query("ALTER TABLE crm_drafts DROP CONSTRAINT IF EXISTS crm_drafts_whatsapp_subject_chk");
    await client.query(
      "ALTER TABLE crm_drafts ADD CONSTRAINT crm_drafts_whatsapp_subject_chk CHECK (channel <> 'whatsapp' OR subject IS NULL)",
    );
    await client.query("COMMIT");
    const { rows } = await client.query<{ conname: string; def: string }>(
      `SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint
       WHERE conname = ANY($1) ORDER BY conname`,
      [[...WIDENED.map(([, name]) => name), "crm_drafts_whatsapp_subject_chk"]],
    );
    for (const row of rows) console.log(`${row.conname}: ${row.def}`);
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
