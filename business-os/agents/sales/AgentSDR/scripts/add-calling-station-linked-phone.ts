/**
 * Cloud calling: adds calling_stations.linked_phone — the WhatsApp account a
 * number's WhatsApp Web is actually logged in as, read by the call worker, so
 * a number linked to the wrong account is caught instead of calling from it.
 * Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-calling-station-linked-phone.ts
 *
 * Additive and re-runnable.
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
    await client.query(`ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS linked_phone text`);
    console.log("calling_stations.linked_phone ready");
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
