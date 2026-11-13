/**
 * Cloud calling: adds calling_stations.link_fresh — a requested link that
 * starts from a logged-out browser, because the session the number holds is
 * the wrong WhatsApp account. Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-calling-station-link-fresh.ts
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
    await client.query(`ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS link_fresh boolean NOT NULL DEFAULT false`);
    console.log("calling_stations.link_fresh ready");
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
