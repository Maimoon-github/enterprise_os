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
    ADD COLUMN IF NOT EXISTS is_parent_company boolean NOT NULL DEFAULT false;
  `);
  await client.query(`
    UPDATE targeted_domains parent
    SET is_parent_company = true
    WHERE EXISTS (
      SELECT 1
      FROM targeted_domains child
      WHERE child.parent_id = parent.id
    );
  `);
  const counts = await client.query(`
    SELECT
      count(*)::int AS total,
      count(*) FILTER (WHERE is_parent_company)::int AS parent_companies
    FROM targeted_domains;
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
