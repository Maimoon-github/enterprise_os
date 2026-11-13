/**
 * Fast category column migration.
 *
 * Strategy: table is CLUSTERed by (country_code, annual_sales).
 * So all rows for a country are physically contiguous on disk.
 * One UPDATE per country = small committed transactions + cache-friendly I/O.
 * Pure SQL string functions — no join, no temp table, no Node.js row parsing.
 *
 * Resumable: WHERE c1 IS NULL skips already-processed rows on restart.
 *
 * Parsing logic (pure SQL):
 *   SPLIT_PART(categories, ':', 1)  → first colon-separated tag
 *   LTRIM(..., '/')                 → strip leading slash
 *   SPLIT_PART(..., '/', 1/2/3)    → hierarchy level
 *   NULLIF(TRIM(...), '')          → null if empty
 */

const postgres = require("postgres");
const fs = require("fs");
const path = require("path");

const envPath = path.join(__dirname, "../.env.local");
if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, "utf8");
  for (const line of envContent.split(/\r?\n/)) {
    const match = line.match(/^([^#=\s]+)\s*=\s*(.*)$/);
    if (match) process.env[match[1].trim()] = match[2].trim().replace(/^"|"$/g, "");
  }
}

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL is not set — see .env.example");
}

const sql = postgres(process.env.DATABASE_URL, {
  ssl: "require",
  max: 3,
});

async function main() {
  // Ensure columns exist (idempotent)
  await sql.unsafe(`ALTER TABLE clean_domains ADD COLUMN IF NOT EXISTS c1 text`);
  await sql.unsafe(`ALTER TABLE clean_domains ADD COLUMN IF NOT EXISTS c2 text`);
  await sql.unsafe(`ALTER TABLE clean_domains ADD COLUMN IF NOT EXISTS c3 text`);

  // Get countries sorted by row count desc so largest batches go first
  const countries = await sql`
    SELECT country_code, COUNT(*) AS cnt
    FROM clean_domains
    WHERE country_code IS NOT NULL
    GROUP BY country_code
    ORDER BY cnt DESC
  `;

  const totalRows = countries.reduce((s, r) => s + Number(r.cnt), 0);
  console.log(`Countries: ${countries.length} | Total rows: ${totalRows.toLocaleString()}`);
  console.log(`Largest: ${countries[0].country_code} (${Number(countries[0].cnt).toLocaleString()} rows)\n`);

  let done = 0;
  const start = Date.now();

  for (const row of countries) {
    const cc = row.country_code;
    const cnt = Number(row.cnt);
    const t = Date.now();

    // Single UPDATE per country — pure SQL string parsing of the categories column
    await sql`
      UPDATE clean_domains
      SET
        c1 = NULLIF(TRIM(SPLIT_PART(LTRIM(SPLIT_PART(categories, ':', 1), '/'), '/', 1)), ''),
        c2 = NULLIF(TRIM(SPLIT_PART(LTRIM(SPLIT_PART(categories, ':', 1), '/'), '/', 2)), ''),
        c3 = NULLIF(TRIM(SPLIT_PART(LTRIM(SPLIT_PART(categories, ':', 1), '/'), '/', 3)), '')
      WHERE country_code = ${cc}
        AND categories IS NOT NULL
        AND c1 IS NULL
    `;

    done += cnt;
    const ms = Date.now() - t;
    const pct = ((done / totalRows) * 100).toFixed(1);
    const eta = Math.round(((Date.now() - start) / done) * (totalRows - done) / 1000);
    console.log(`  ${cc.padEnd(4)} ${cnt.toLocaleString().padStart(9)} rows  ${ms}ms  |  ${pct}%  ETA ${eta}s`);
  }

  console.log(`\nAll rows updated in ${((Date.now() - start) / 1000).toFixed(1)}s`);

  // Indexes
  console.log("\nCreating indexes CONCURRENTLY...");

  const t1 = Date.now();
  await sql`
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clean_country_c1
    ON clean_domains (country_code, c1)
    WHERE c1 IS NOT NULL
  `;
  console.log(`  (country_code, c1)       ${((Date.now() - t1) / 1000).toFixed(1)}s`);

  const t2 = Date.now();
  await sql`
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clean_country_c1_c2
    ON clean_domains (country_code, c1, c2)
    WHERE c2 IS NOT NULL
  `;
  console.log(`  (country_code, c1, c2)   ${((Date.now() - t2) / 1000).toFixed(1)}s`);

  await sql`ANALYZE clean_domains`;

  const stats = await sql`
    SELECT
      COUNT(*) FILTER (WHERE c1 IS NOT NULL) AS with_c1,
      COUNT(*) FILTER (WHERE c2 IS NOT NULL) AS with_c2,
      COUNT(*) FILTER (WHERE c3 IS NOT NULL) AS with_c3,
      COUNT(DISTINCT c1) AS unique_c1,
      COUNT(DISTINCT c2) AS unique_c2
    FROM clean_domains
  `;
  console.log("\nStats:", stats[0]);

  await sql.end();
}

main().catch((e) => { console.error(e); process.exit(1); });
