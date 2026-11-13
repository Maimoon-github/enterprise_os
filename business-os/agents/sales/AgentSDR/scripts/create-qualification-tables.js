const { Client } = require("pg");
const fs = require("fs");
const path = require("path");

// Load .env.local manually (same pattern as the other scripts)
const envPath = path.join(__dirname, "../.env.local");
const envContent = fs.readFileSync(envPath, "utf8");
for (const line of envContent.split("\n")) {
  const m = line.match(/^([^=]+)=(.*)$/);
  if (m) process.env[m[1].trim()] = m[2].trim().replace(/^"|"$/g, "");
}

// Surgical: only creates the three new pipeline tables. IF NOT EXISTS makes it
// safe to re-run, and it never touches the existing domains / clean_domains tables.
const SQL = `
CREATE TABLE IF NOT EXISTS campaigns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  input_mode text NOT NULL,
  filters jsonb,
  job_titles text[],
  target_lead_count integer NOT NULL DEFAULT 3000,
  accumulated_lead_count integer NOT NULL DEFAULT 0,
  apollo_link text,
  status text NOT NULL DEFAULT 'building',
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS targeted_domains (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  domain text NOT NULL UNIQUE,
  campaign_id uuid REFERENCES campaigns(id),
  status text NOT NULL DEFAULT 'pending',
  is_live boolean,
  is_running_ads boolean,
  apollo_org_id text,
  apollo_lead_count integer,
  apollo_org_employee_estimate integer,
  expected_employee_count integer,
  coverage_ratio numeric,
  parent_company text,
  parent_domain text,
  reason text,
  qualification_debug jsonb,
  checked_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_targeted_domains_campaign ON targeted_domains (campaign_id);
CREATE INDEX IF NOT EXISTS idx_targeted_domains_status ON targeted_domains (status);

CREATE TABLE IF NOT EXISTS qualification_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id uuid NOT NULL REFERENCES campaigns(id),
  status text NOT NULL DEFAULT 'running',
  domains_processed integer NOT NULL DEFAULT 0,
  domains_qualified integer NOT NULL DEFAULT 0,
  started_at timestamptz DEFAULT now(),
  finished_at timestamptz
);
`;

async function main() {
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
  });
  await client.connect();
  console.log("Creating qualification pipeline tables...");
  await client.query(SQL);

  const { rows } = await client.query(
    `SELECT table_name FROM information_schema.tables
     WHERE table_name IN ('campaigns','targeted_domains','qualification_jobs')
     ORDER BY table_name`,
  );
  console.log("Tables present:", rows.map((r) => r.table_name).join(", "));
  await client.end();
  console.log("Done.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
