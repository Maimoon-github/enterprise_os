const { Client } = require("pg");
const fs = require("fs");
const path = require("path");

const envPath = path.join(__dirname, "../.env.local");
const envContent = fs.readFileSync(envPath, "utf8");
for (const line of envContent.split("\n")) {
  const m = line.match(/^([^=]+)=(.*)$/);
  if (m) process.env[m[1].trim()] = m[2].trim().replace(/^"|"$/g, "");
}

const SQL = `
ALTER TABLE targeted_domains ADD COLUMN IF NOT EXISTS qualification_debug jsonb;
`;

async function main() {
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
  });
  await client.connect();
  console.log("Adding qualification_debug to targeted_domains...");
  await client.query(SQL);

  const { rows } = await client.query(
    `SELECT column_name FROM information_schema.columns
     WHERE table_name = 'targeted_domains'
       AND column_name = 'qualification_debug'`,
  );
  console.log("Column present:", rows.length > 0);
  await client.end();
  console.log("Done.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
