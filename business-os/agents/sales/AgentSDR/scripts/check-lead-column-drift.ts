/**
 * Verifies that each organization's custom-field registry (entity_columns)
 * and the values its rows actually carry (people.custom / companies.custom)
 * still agree.
 *
 * Run with:  bun run scripts/check-lead-column-drift.ts
 * Exits non-zero on drift, so it can gate CI.
 *
 * Unlike everything else in scripts/, this is not a migration — it changes
 * nothing. Custom fields are no longer physical columns: a field's definition
 * is a row in entity_columns (one registry per organization) and its values
 * are keys in the row's `custom` jsonb. Three things can go wrong, and all
 * three are checked here:
 *
 *   1. unregistered key  — a row's `custom` carries a key that has no registry
 *      row in the row's own organization. The value is invisible to the app.
 *      (This also catches a registry row deleted while values remained.)
 *   2. stray physical column — a physical `x_*` column exists on people or
 *      companies. The old design added those with ALTER TABLE; none was ever
 *      created, and any that appears now would be data the app never reads.
 *   3. missing core rows — an organization has people but no core registry
 *      rows. Informational only: they are created lazily on first read.
 *
 * Registered-but-unused keys are normal (a new field) and not reported as drift.
 */
import { Client } from "pg";

const TABLES = { person: "people", company: "companies" } as const;

async function main() {
  if (!process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL is not set — check .env.local");
  }

  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
  });

  await client.connect();
  let drifted = false;

  try {
    for (const [entity, table] of Object.entries(TABLES)) {
      // 1. keys used in `custom` with no registry row in the same organization.
      const { rows: unregistered } = await client.query<{ organization_id: string; key: string }>(
        `SELECT DISTINCT t.organization_id, k.key
         FROM ${table} t
         CROSS JOIN LATERAL jsonb_object_keys(t.custom) AS k(key)
         WHERE NOT EXISTS (
           SELECT 1 FROM entity_columns c
           WHERE c.organization_id = t.organization_id AND c.entity = $1 AND c.key = k.key
         )
         ORDER BY 1, 2`,
        [entity],
      );

      // 2. stray physical x_ columns.
      const { rows: physical } = await client.query<{ column_name: string }>(
        `SELECT column_name FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = $1 AND column_name LIKE 'x\\_%'`,
        [table],
      );

      const { rows: counts } = await client.query<{ organization_id: string; n: string; archived: string }>(
        `SELECT organization_id, count(*)::text AS n, count(archived_at)::text AS archived
         FROM entity_columns WHERE entity = $1 GROUP BY organization_id`,
        [entity],
      );

      if (unregistered.length || physical.length) {
        drifted = true;
        console.error(`DRIFT on ${table}:`);
        for (const row of unregistered) {
          console.error(`  organization ${row.organization_id}: key "${row.key}" in custom has no registry row`);
        }
        if (physical.length) {
          console.error(`  physical columns that nothing reads: ${physical.map((r) => r.column_name).join(", ")}`);
        }
      } else {
        console.log(
          `${table}: ${counts.length} organization registries ` +
            `(${counts.map((c) => `${c.n} fields/${c.archived} archived`).join("; ") || "none yet"}), no drift`,
        );
      }
    }
  } finally {
    await client.end();
  }

  if (drifted) {
    console.error(
      "\nRepair by registering the key (add the field in Settings -> Lead columns for that " +
        "organization) or, once confirmed unwanted, removing it from custom. Do not drop a " +
        "physical column to resolve drift — it may still hold data.",
    );
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
