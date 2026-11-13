/**
 * Cloud calling: creates calling_proxies (the outbound IPs calling numbers
 * use) and adds to calling_stations the assigned proxy, the CloakBrowser
 * fingerprint seed, and the saved-profile columns. Matches
 * src/lib/calls/schema.ts; see src/lib/calls/stationContract.ts.
 *
 * Run with:  bun run scripts/create-calling-proxies.ts
 *
 * Additive only (a new table; nullable or defaulted columns). Existing
 * numbers each get a random fingerprint seed from the column default.
 * Re-runnable: everything is guarded.
 */
import { Client } from "pg";

const STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS calling_proxies (
     organization_id uuid NOT NULL REFERENCES organizations(id),
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     label text NOT NULL,
     protocol text NOT NULL,
     host text NOT NULL,
     port integer NOT NULL,
     username text,
     password_encrypted text,
     country text,
     timezone text,
     provider text,
     notes text,
     created_at timestamptz NOT NULL DEFAULT now(),
     updated_at timestamptz NOT NULL DEFAULT now(),
     CONSTRAINT calling_proxies_protocol_chk CHECK (protocol IN ('http', 'socks5')),
     CONSTRAINT calling_proxies_port_chk CHECK (port BETWEEN 1 AND 65535)
   )`,
  `CREATE INDEX IF NOT EXISTS calling_proxies_organization_idx ON calling_proxies (organization_id)`,

  `ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS proxy_id uuid`,
  `ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS fingerprint_seed integer NOT NULL DEFAULT (floor(random() * 90000) + 10000)::int`,
  `ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS profile_key text`,
  `ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS profile_bytes integer`,
  `ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS profile_version integer NOT NULL DEFAULT 0`,
  `ALTER TABLE calling_stations ADD COLUMN IF NOT EXISTS profile_saved_at timestamptz`,
  `DO $$ BEGIN
     IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'calling_stations_proxy_fk') THEN
       ALTER TABLE calling_stations ADD CONSTRAINT calling_stations_proxy_fk
         FOREIGN KEY (proxy_id) REFERENCES calling_proxies(id) ON DELETE SET NULL;
     END IF;
     IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'calling_stations_seed_chk') THEN
       ALTER TABLE calling_stations ADD CONSTRAINT calling_stations_seed_chk CHECK (fingerprint_seed BETWEEN 10000 AND 99999);
     END IF;
   END $$`,
  // One number per IP.
  `CREATE UNIQUE INDEX IF NOT EXISTS calling_stations_proxy_uq ON calling_stations (proxy_id) WHERE proxy_id IS NOT NULL`,
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
    const { rows } = await client.query<{ name: string; seed: number }>(
      `SELECT name, fingerprint_seed AS seed FROM calling_stations ORDER BY created_at`,
    );
    console.log(`calling_proxies ready; numbers: ${rows.map((row) => `${row.name} (seed ${row.seed})`).join(", ") || "none"}`);
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
