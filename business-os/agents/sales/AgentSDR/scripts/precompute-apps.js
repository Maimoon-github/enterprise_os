const { Client } = require("pg");
const fs = require("fs");
const path = require("path");

// Load .env.local manually
const envPath = path.join(__dirname, "../.env.local");
const envContent = fs.readFileSync(envPath, "utf8");
for (const line of envContent.split("\n")) {
  const m = line.match(/^([^=]+)=(.*)$/);
  if (m) process.env[m[1].trim()] = m[2].trim().replace(/^"|"$/g, "");
}

async function main() {
  const client = new Client({ connectionString: process.env.DATABASE_URL, ssl: { rejectUnauthorized: false } });
  await client.connect();

  console.log("Fetching all apps globally...");
  const start = Date.now();

  const r = await client.query(`
    SELECT trim(app) AS app, COUNT(*)::int AS cnt
    FROM clean_domains,
    LATERAL regexp_split_to_table(installed_apps_names, ':') AS app
    WHERE installed_apps_names IS NOT NULL
    GROUP BY trim(app)
    HAVING trim(app) != ''
    ORDER BY cnt DESC
  `);

  await client.end();
  console.log(`Done: ${r.rows.length} apps in ${Date.now() - start}ms`);

  // Simple array of [name, count] sorted by count desc
  const result = r.rows.map(row => ({ name: row.app, count: row.cnt }));

  const outPath = path.join(__dirname, "../src/data/apps.json");
  fs.writeFileSync(outPath, JSON.stringify(result, null, 2));
  console.log(`Wrote ${outPath}`);
}

main().catch(console.error);
