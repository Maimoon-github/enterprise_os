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

// The Postgres equivalent of AgentSDR-app's per-mailbox Redis send queue
// (mailbox:<id>:sendMailQueue). build-mailbox-queue.ts writes one row per
// lead due to send today, ordered by priority; the tick handler pops the
// lowest-position row for each mailbox and deletes it after sending.
const SQL = `
CREATE TABLE IF NOT EXISTS outreach_mailbox_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mailbox_id uuid NOT NULL REFERENCES outreach_mailboxes(id) ON DELETE CASCADE,
  lead_id uuid NOT NULL REFERENCES outreach_leads(id) ON DELETE CASCADE,
  position integer NOT NULL,
  created_at timestamptz DEFAULT now(),
  UNIQUE (mailbox_id, lead_id)
);

CREATE INDEX IF NOT EXISTS idx_outreach_mailbox_queue_mailbox_position
  ON outreach_mailbox_queue (mailbox_id, position);
`;

async function main() {
  await client.connect();
  console.log("Creating outreach_mailbox_queue table...");
  await client.query(SQL);

  const { rows } = await client.query(`
    SELECT table_name FROM information_schema.tables WHERE table_name = 'outreach_mailbox_queue'
  `);
  console.log("Table present:", rows.length > 0);
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await client.end();
  });
