/**
 * Pre-computes category counts per country and saves to src/data/category-counts.json.
 * Run this once after DB migrations. CategoryFilter reads from this JSON directly — zero API calls.
 */

const postgres = require("postgres");
const fs = require("fs");
const path = require("path");

// Connection comes from DATABASE_URL in .env.local, like every other script
// here. It was previously hardcoded, password included, which is not
// something that can live in a tracked file.
const envPath = path.join(__dirname, "../.env.local");
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
    const m = line.match(/^([^=#]+)=(.*)$/);
    if (m) process.env[m[1].trim()] ??= m[2].trim().replace(/^"|"$/g, "");
  }
}

if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL not set in .env.local");
const sql = postgres(process.env.DATABASE_URL, { ssl: "require", max: 5 });

async function main() {
  console.time("total");

  console.log("Running 4 aggregate queries in parallel...");
  const [c1Rows, c2Rows, c3Rows, nullRows] = await Promise.all([
    // C1 counts per country
    sql`
      SELECT country_code, c1, COUNT(*)::int AS cnt
      FROM clean_domains
      WHERE c1 IS NOT NULL
      GROUP BY country_code, c1
    `,
    // C2 counts per country + c1
    sql`
      SELECT country_code, c1, c2, COUNT(*)::int AS cnt
      FROM clean_domains
      WHERE c2 IS NOT NULL
      GROUP BY country_code, c1, c2
    `,
    // C3 counts per country + c1 + c2
    sql`
      SELECT country_code, c1, c2, c3, COUNT(*)::int AS cnt
      FROM clean_domains
      WHERE c3 IS NOT NULL
      GROUP BY country_code, c1, c2, c3
    `,
    // Null-c1 counts per country
    sql`
      SELECT country_code, COUNT(*)::int AS cnt
      FROM clean_domains
      WHERE c1 IS NULL
      GROUP BY country_code
    `,
  ]);

  console.log(`  c1 rows: ${c1Rows.length}, c2 rows: ${c2Rows.length}, c3 rows: ${c3Rows.length}, null rows: ${nullRows.length}`);

  // Build nested map: counts.c1[country][c1_val] = count
  const counts = { c1: {}, c2: {}, c3: {} };

  // C1 counts (+ null sentinel)
  for (const r of c1Rows) {
    const cc = r.country_code;
    if (!counts.c1[cc]) counts.c1[cc] = {};
    counts.c1[cc][r.c1] = r.cnt;
  }
  for (const r of nullRows) {
    const cc = r.country_code;
    if (!counts.c1[cc]) counts.c1[cc] = {};
    counts.c1[cc]["__null__"] = r.cnt;
  }

  // C2 counts: counts.c2[country][c1][c2] = count
  for (const r of c2Rows) {
    const cc = r.country_code;
    if (!counts.c2[cc]) counts.c2[cc] = {};
    if (!counts.c2[cc][r.c1]) counts.c2[cc][r.c1] = {};
    counts.c2[cc][r.c1][r.c2] = r.cnt;
  }

  // C3 counts: counts.c3[country][c1|c2][c3] = count
  for (const r of c3Rows) {
    const cc = r.country_code;
    const key = `${r.c1}|${r.c2}`;
    if (!counts.c3[cc]) counts.c3[cc] = {};
    if (!counts.c3[cc][key]) counts.c3[cc][key] = {};
    counts.c3[cc][key][r.c3] = r.cnt;
  }

  const outPath = path.join(__dirname, "../src/data/category-counts.json");
  fs.writeFileSync(outPath, JSON.stringify(counts));

  const size = (fs.statSync(outPath).size / 1024).toFixed(1);
  console.log(`\nSaved to src/data/category-counts.json (${size} KB)`);
  console.timeEnd("total");

  await sql.end();
}

main().catch((e) => { console.error(e); process.exit(1); });
