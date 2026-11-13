/**
 * Creates whatsapp_accounts, whatsapp_chats and whatsapp_messages — WhatsApp
 * messaging through Unipile. Matches src/lib/whatsapp/schema.ts.
 *
 * Run with:  bun run scripts/create-whatsapp-tables.ts
 *
 * New tables only; nothing existing changes. Re-runnable: every table,
 * index and constraint is guarded.
 */
import { Client } from "pg";

const STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS whatsapp_accounts (
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     unipile_account_id text NOT NULL,
     name text,
     phone text,
     status text NOT NULL DEFAULT 'connected',
     connected_at timestamptz,
     is_default boolean NOT NULL DEFAULT false,
     last_synced_at timestamptz,
     created_at timestamptz NOT NULL DEFAULT now(),
     updated_at timestamptz NOT NULL DEFAULT now(),
     CONSTRAINT whatsapp_accounts_unipile_account_uq UNIQUE (unipile_account_id),
     CONSTRAINT whatsapp_accounts_status_chk CHECK (status IN ('connected', 'disconnected', 'credentials', 'error'))
   )`,
  `CREATE TABLE IF NOT EXISTS whatsapp_chats (
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     account_id uuid NOT NULL,
     unipile_chat_id text NOT NULL,
     provider_id text,
     phone text,
     person_id uuid,
     name text,
     last_message_at timestamptz,
     last_message_preview text,
     last_direction text,
     unread_count integer NOT NULL DEFAULT 0,
     created_at timestamptz NOT NULL DEFAULT now(),
     updated_at timestamptz NOT NULL DEFAULT now(),
     CONSTRAINT whatsapp_chats_account_fk FOREIGN KEY (account_id) REFERENCES whatsapp_accounts(id) ON DELETE CASCADE,
     CONSTRAINT whatsapp_chats_person_fk FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE SET NULL,
     CONSTRAINT whatsapp_chats_account_chat_uq UNIQUE (account_id, unipile_chat_id),
     CONSTRAINT whatsapp_chats_unread_chk CHECK (unread_count >= 0),
     CONSTRAINT whatsapp_chats_last_direction_chk CHECK (last_direction IS NULL OR last_direction IN ('inbound', 'outbound'))
   )`,
  `CREATE INDEX IF NOT EXISTS whatsapp_chats_account_last_message_idx ON whatsapp_chats (account_id, last_message_at)`,
  `CREATE INDEX IF NOT EXISTS whatsapp_chats_person_idx ON whatsapp_chats (person_id)`,
  `CREATE INDEX IF NOT EXISTS whatsapp_chats_phone_idx ON whatsapp_chats (phone)`,
  `CREATE TABLE IF NOT EXISTS whatsapp_messages (
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     chat_id uuid NOT NULL,
     unipile_message_id text,
     direction text NOT NULL,
     origin text NOT NULL,
     body text NOT NULL DEFAULT '',
     attachments jsonb NOT NULL DEFAULT '[]'::jsonb,
     sent_at timestamptz NOT NULL,
     delivered_at timestamptz,
     read_at timestamptz,
     crm_conversation_message_id uuid,
     call_session_id uuid,
     raw jsonb,
     created_at timestamptz NOT NULL DEFAULT now(),
     CONSTRAINT whatsapp_messages_chat_fk FOREIGN KEY (chat_id) REFERENCES whatsapp_chats(id) ON DELETE CASCADE,
     CONSTRAINT whatsapp_messages_crm_message_fk FOREIGN KEY (crm_conversation_message_id) REFERENCES crm_conversation_messages(id) ON DELETE SET NULL,
     CONSTRAINT whatsapp_messages_call_session_fk FOREIGN KEY (call_session_id) REFERENCES call_sessions(id) ON DELETE SET NULL,
     CONSTRAINT whatsapp_messages_direction_chk CHECK (direction IN ('inbound', 'outbound')),
     CONSTRAINT whatsapp_messages_origin_chk CHECK (origin IN ('lead', 'agentsdr', 'phone')),
     CONSTRAINT whatsapp_messages_origin_direction_chk CHECK ((direction = 'inbound') = (origin = 'lead'))
   )`,
  `CREATE UNIQUE INDEX IF NOT EXISTS whatsapp_messages_unipile_message_uq ON whatsapp_messages (unipile_message_id) WHERE unipile_message_id IS NOT NULL`,
  `CREATE INDEX IF NOT EXISTS whatsapp_messages_chat_sent_idx ON whatsapp_messages (chat_id, sent_at)`,
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
    for (const statement of STATEMENTS) await client.query(statement);
    await client.query("COMMIT");
    const { rows } = await client.query<{ table_name: string }>(
      `SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'whatsapp\\_%' ORDER BY table_name`,
    );
    console.log(`tables: ${rows.map((row) => row.table_name).join(", ")}`);
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
