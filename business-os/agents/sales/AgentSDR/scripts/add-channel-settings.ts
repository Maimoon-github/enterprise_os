/**
 * Sending rules per organization (Settings → Email / LinkedIn / WhatsApp →
 * Sending rules), replacing numbers that were hardcoded in the sending
 * engines. Matches src/lib/channels/schema.ts, the two override columns in
 * src/lib/linkedin/schema.ts and src/lib/whatsapp/schema.ts, and
 * src/lib/tenancy/registry.ts.
 *
 * Run with:  bun run scripts/add-channel-settings.ts
 *
 * - channel_settings: one row per (organization, channel); `values` holds
 *   only what the organization changed. No row = today's defaults, so the
 *   table can be created before or after the code that reads it is deployed.
 * - "LinkedInAccount"."dailyInviteLimit", whatsapp_accounts.new_chats_per_day:
 *   per-account overrides, nullable (null = the organization's rule).
 *
 * Additive and re-runnable: every statement is guarded.
 */
import { Client } from "pg";

const STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS channel_settings (
     organization_id uuid NOT NULL REFERENCES organizations(id),
     channel text NOT NULL,
     values jsonb NOT NULL DEFAULT '{}'::jsonb,
     updated_by text,
     updated_at timestamptz NOT NULL DEFAULT now(),
     CONSTRAINT channel_settings_pkey PRIMARY KEY (organization_id, channel)
   )`,
  `ALTER TABLE "LinkedInAccount" ADD COLUMN IF NOT EXISTS "dailyInviteLimit" integer`,
  `ALTER TABLE whatsapp_accounts ADD COLUMN IF NOT EXISTS new_chats_per_day integer`,
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
    for (const statement of STATEMENTS) await client.query(statement);
    const { rows } = await client.query<{ what: string; present: boolean }>(`
      SELECT 'channel_settings' AS what, to_regclass('public.channel_settings') IS NOT NULL AS present
      UNION ALL
      SELECT '"LinkedInAccount"."dailyInviteLimit"', EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'LinkedInAccount' AND column_name = 'dailyInviteLimit')
      UNION ALL
      SELECT 'whatsapp_accounts.new_chats_per_day', EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'whatsapp_accounts' AND column_name = 'new_chats_per_day')`);
    for (const row of rows) console.log(`${row.what} ${row.present ? "present" : "MISSING"}`);
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
