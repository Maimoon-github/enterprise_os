const { Client } = require("pg");
const fs = require("fs");
const path = require("path");

const envContent = fs.readFileSync(path.join(__dirname, "../.env.local"), "utf8");
for (const line of envContent.split("\n")) {
  const m = line.match(/^([^=]+)=(.*)$/);
  if (m) process.env[m[1].trim()] = m[2].trim().replace(/^"|"$/g, "");
}

const COUNTRIES = ["US", "GB", "CA", "AU", "IN", "DE", "FR", "NL", "BR", "MX", "SG", "NZ", "SE", "NO", "DK"];

async function main() {
  const client = new Client({ connectionString: process.env.DATABASE_URL, ssl: { rejectUnauthorized: false } });
  await client.connect();

  // Add column if not exists
  console.log("Adding installed_apps_array column...");
  await client.query(`
    ALTER TABLE clean_domains
    ADD COLUMN IF NOT EXISTS installed_apps_array text[]
  `);

  // Populate per country
  for (const cc of COUNTRIES) {
    process.stdout.write(`Updating ${cc}... `);
    const start = Date.now();
    const r = await client.query(`
      UPDATE clean_domains
      SET installed_apps_array = (
        SELECT array_agg(trim(app))
        FROM regexp_split_to_table(installed_apps_names, ':') AS app
        WHERE trim(app) != ''
      )
      WHERE country_code = $1
        AND installed_apps_names IS NOT NULL
        AND installed_apps_array IS NULL
    `, [cc]);
    console.log(`${r.rowCount} rows (${Date.now() - start}ms)`);
  }

  // GIN index
  console.log("Creating GIN index...");
  await client.query(`
    CREATE INDEX IF NOT EXISTS idx_clean_domains_apps_gin
    ON clean_domains USING GIN (installed_apps_array)
  `);
  console.log("Done.");

  await client.end();
}

main().catch(console.error);
