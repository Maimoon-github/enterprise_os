const { Client } = require("pg");
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

const client = new Client({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
});

async function main() {
  await client.connect();
  await client.query(`
    ALTER TABLE targeted_domains
    ADD COLUMN IF NOT EXISTS revenue numeric;
  `);

  // Backfill existing rows from clean_domains.annual_sales where possible.
  await client.query(`
    UPDATE targeted_domains td
    SET revenue = cd.annual_sales
    FROM clean_domains cd
    WHERE td.revenue IS NULL
      AND regexp_replace(lower(cd.domain), '^www\\.', '') = td.domain;
  `);

  // Parent-company rows: copy the revenue of the child(ren) that point to them.
  await client.query(`
    UPDATE targeted_domains parent
    SET revenue = child.revenue
    FROM targeted_domains child
    WHERE parent.revenue IS NULL
      AND parent.is_parent_company = true
      AND child.parent_id = parent.id
      AND child.revenue IS NOT NULL;
  `);

  const counts = await client.query(`
    SELECT count(*)::int AS total, count(revenue)::int AS with_revenue FROM targeted_domains;
  `);
  console.log(counts.rows[0]);
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await client.end();
  });
