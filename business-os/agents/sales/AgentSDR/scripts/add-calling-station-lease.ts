/**
 * Cloud calling: adds calling_stations.lease_holder / lease_until — the call
 * worker that keeps the number's WhatsApp Web open, and until when (renewed
 * every 20 s). Only the holder runs the number's calls and links, so its
 * browser profile is never open in two places; a lease left to expire (the
 * worker died) frees the number for another. Matches src/lib/calls/schema.ts.
 *
 * Run with:  bun run scripts/add-calling-station-lease.ts
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
    await client.query(`ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS lease_holder text`);
    await client.query(`ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS lease_until timestamp with time zone`);
    console.log("calling_stations.lease_holder / lease_until ready");
  } finally {
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
