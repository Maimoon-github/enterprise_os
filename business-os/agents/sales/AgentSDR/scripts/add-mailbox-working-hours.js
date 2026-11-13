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

const DEFAULT_WORKING_HOURS = {
  timezone: "Asia/Kolkata",
  days: {
    monday: { enabled: true, from: "09:00", to: "18:00" },
    tuesday: { enabled: true, from: "09:00", to: "18:00" },
    wednesday: { enabled: true, from: "09:00", to: "18:00" },
    thursday: { enabled: true, from: "09:00", to: "18:00" },
    friday: { enabled: true, from: "09:00", to: "18:00" },
    saturday: { enabled: false, from: "09:00", to: "18:00" },
    sunday: { enabled: false, from: "09:00", to: "18:00" },
  },
};

// Adds a per-mailbox working-hours window so the scheduler stops sending
// outside business hours (previously unbounded — see audit findings).
// Defaults every existing mailbox to Mon-Fri 9-6 ET so nothing silently
// stops sending after this migration.
async function main() {
  await client.connect();
  console.log("Adding working_hours column to outreach_mailboxes...");
  await client.query(`
    ALTER TABLE outreach_mailboxes
    ADD COLUMN IF NOT EXISTS working_hours jsonb NOT NULL DEFAULT '${JSON.stringify(DEFAULT_WORKING_HOURS)}'::jsonb;
  `);

  const { rows } = await client.query(`
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'outreach_mailboxes' AND column_name = 'working_hours'
  `);
  console.log("working_hours column present:", rows.length > 0);
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await client.end();
  });
