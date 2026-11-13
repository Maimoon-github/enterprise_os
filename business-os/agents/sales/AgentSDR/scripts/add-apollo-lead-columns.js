const { Client } = require("pg");
const fs = require("fs");
const path = require("path");

const envPath = path.join(__dirname, "../.env.local");
const envContent = fs.readFileSync(envPath, "utf8");
for (const line of envContent.split("\n")) {
  const m = line.match(/^([^=]+)=(.*)$/);
  if (m) process.env[m[1].trim()] = m[2].trim().replace(/^"|"$/g, "");
}

// Adds all_lead_count and parent_id columns. Idempotent.
const SQL = `
ALTER TABLE targeted_domains ADD COLUMN IF NOT EXISTS all_lead_count integer;
ALTER TABLE targeted_domains ADD COLUMN IF NOT EXISTS parent_id uuid;
CREATE INDEX IF NOT EXISTS idx_targeted_domains_parent_id ON targeted_domains (parent_id);
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
       AND column_name IN ('all_lead_count','parent_id')
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
