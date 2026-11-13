const { Client } = require("pg");
const fs = require("fs");
const path = require("path");

const envPath = path.join(__dirname, "../.env.local");
const envContent = fs.readFileSync(envPath, "utf8");
for (const line of envContent.split("\n")) {
  const m = line.match(/^([^=]+)=(.*)$/);
  if (m) process.env[m[1].trim()] = m[2].trim().replace(/^"|"$/g, "");
}

// Add the columns the simplified pipeline needs. Idempotent.
const SQL = `
ALTER TABLE targeted_domains ADD COLUMN IF NOT EXISTS verified_employee_count integer;
ALTER TABLE targeted_domains ADD COLUMN IF NOT EXISTS parent_pending boolean NOT NULL DEFAULT false;
ALTER TABLE targeted_domains ADD COLUMN IF NOT EXISTS parent_domain text;
ALTER TABLE targeted_domains ADD COLUMN IF NOT EXISTS qualification_debug jsonb;
CREATE INDEX IF NOT EXISTS idx_targeted_domains_parent_pending ON targeted_domains (parent_pending);
`;

async function main() {
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
  });
  await client.connect();
  console.log("Altering targeted_domains...");
  await client.query(SQL);

  const { rows } = await client.query(
    `SELECT column_name FROM information_schema.columns
     WHERE table_name = 'targeted_domains'
       AND column_name IN ('verified_employee_count','parent_pending','parent_domain','qualification_debug')
     ORDER BY column_name`,
  );
  console.log("Columns present:", rows.map((r) => r.column_name).join(", "));
  await client.end();
  console.log("Done.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
