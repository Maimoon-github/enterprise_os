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
    ALTER TABLE qualification_jobs
    ADD COLUMN IF NOT EXISTS requested_limit integer,
    ADD COLUMN IF NOT EXISTS current_domain text,
    ADD COLUMN IF NOT EXISTS last_heartbeat_at timestamptz;
  `);
  await client.query(`
    UPDATE qualification_jobs
    SET last_heartbeat_at = COALESCE(last_heartbeat_at, started_at)
    WHERE status = 'running';
  `);
  const counts = await client.query(`
    SELECT
      count(*)::int AS total,
      count(*) FILTER (WHERE status = 'running')::int AS running
    FROM qualification_jobs;
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
