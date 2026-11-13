/**
 * Adds people.phone — the number the WhatsApp Call button dials — as a core
 * column.
 *
 * Run with:  bun run scripts/add-people-phone.ts
 *
 * Registered in entity_columns in the same transaction as the ALTER, matching
 * the CORE_COLUMNS entry in create-lead-tables.ts, so
 * scripts/check-lead-column-drift.ts keeps passing. Stored as E.164 text
 * (normalizePhone in src/lib/calls/phone.ts). Deliberately not unique: an
 * office switchboard is shared by everyone at the company.
 *
 * No backfill: on 29 Sep 2026 no import had kept a phone under a top-level
 * raw key, so there was nothing to lift.
 *
 * Re-runnable: every statement is guarded.
 */
import { Client } from "pg";

const SQL = `
ALTER TABLE people ADD COLUMN IF NOT EXISTS phone text;

CREATE INDEX IF NOT EXISTS people_phone_lookup_idx ON people (phone) WHERE phone IS NOT NULL;

INSERT INTO entity_columns (entity, key, name, type, pg_type, is_core, position)
VALUES ('person', 'phone', 'Phone', 'text', 'text', true,
        (SELECT coalesce(max(position), 0) + 1 FROM entity_columns WHERE entity = 'person'))
ON CONFLICT (entity, key) DO UPDATE SET is_core = true, updated_at = now();
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
    await client.query(SQL);
    await client.query("COMMIT");
    const { rows } = await client.query<{ total: string; with_phone: string }>(
      `SELECT count(*)::text AS total, count(phone)::text AS with_phone FROM people`,
    );
    console.log(`people: ${rows[0].with_phone} of ${rows[0].total} have a phone`);
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
