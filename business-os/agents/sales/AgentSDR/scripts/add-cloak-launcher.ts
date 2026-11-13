/**
 * Cloud calling: allows the "cloak" launcher (CloakBrowser) on
 * calling_stations and makes it the default. Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-cloak-launcher.ts
 *
 * Re-runnable: the check constraint is replaced only while it lacks 'cloak'.
 */
import { Client } from "pg";

const STATEMENTS = [
  `DO $$ BEGIN
     IF NOT EXISTS (
       SELECT 1 FROM pg_constraint
        WHERE conname = 'calling_stations_launcher_chk' AND pg_get_constraintdef(oid) LIKE '%cloak%'
     ) THEN
       ALTER TABLE calling_stations DROP CONSTRAINT IF EXISTS calling_stations_launcher_chk;
       ALTER TABLE calling_stations ADD CONSTRAINT calling_stations_launcher_chk
         CHECK (launcher IN ('cloak', 'local', 'gologin_sdk', 'gologin_cloud'));
     END IF;
   END $$`,
  `ALTER TABLE calling_stations ALTER COLUMN launcher SET DEFAULT 'cloak'`,
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
    await client.query("BEGIN");
    for (const statement of STATEMENTS) await client.query(statement);
    await client.query("COMMIT");
    const { rows } = await client.query<{ def: string }>(
      `SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint WHERE conname = 'calling_stations_launcher_chk'`,
    );
    console.log(`calling_stations_launcher_chk: ${rows[0]?.def ?? "missing"}`);
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
