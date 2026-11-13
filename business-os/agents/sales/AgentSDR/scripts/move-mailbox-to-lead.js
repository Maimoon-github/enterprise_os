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

// Moves mailbox assignment from outreach_campaigns to outreach_leads —
// mailbox pool is shared across all active campaigns (round-robin per lead
// at first-send time), not locked one-per-campaign. Both tables are empty
// at the time this was written, so this is a straight column move.
const SQL = `
ALTER TABLE outreach_campaigns DROP COLUMN IF EXISTS mailbox_id;
ALTER TABLE outreach_leads ADD COLUMN IF NOT EXISTS mailbox_id uuid REFERENCES outreach_mailboxes(id);
`;

async function main() {
  await client.connect();
  console.log("Moving mailbox_id from outreach_campaigns to outreach_leads...");
  await client.query(SQL);

  const { rows } = await client.query(`
    SELECT table_name, column_name FROM information_schema.columns
    WHERE table_name IN ('outreach_campaigns', 'outreach_leads') AND column_name = 'mailbox_id'
    ORDER BY table_name
  `);
  console.log("mailbox_id now present on:", rows.map((r) => r.table_name).join(", "));
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await client.end();
  });
