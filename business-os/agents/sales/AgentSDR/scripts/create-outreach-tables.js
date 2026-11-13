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

// Outreach sending tables — ported from AgentSDR-app's mailbox/campaign/lead/
// email model, scoped down (no domain-purchasing/warmup-vendor tables; those
// stay out of scope per the migration plan). IF NOT EXISTS makes this safe
// to re-run.
const SQL = `
CREATE TABLE IF NOT EXISTS outreach_mailboxes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email_address text NOT NULL UNIQUE,
  display_name text,
  status text NOT NULL DEFAULT 'connecting',
  last_error text,
  last_tested_at timestamptz,
  last_history_id text,
  daily_send_limit integer NOT NULL DEFAULT 30,
  today_emails_sent integer NOT NULL DEFAULT 0,
  send_counter_reset_at timestamptz,
  next_email_time timestamptz,
  signature_html text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outreach_suppression_list (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE,
  reason text NOT NULL,
  note text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outreach_campaigns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  status text NOT NULL DEFAULT 'draft',
  sequence jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- mailbox_id lives on the lead, not the campaign: assigned round-robin
-- across connected mailboxes with spare capacity when a lead's first email
-- actually sends, so several active campaigns can share one mailbox pool
-- (matches AgentSDR-app's make-mailbox-queue-for-team.ts model).
CREATE TABLE IF NOT EXISTS outreach_leads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id uuid NOT NULL REFERENCES outreach_campaigns(id) ON DELETE CASCADE,
  mailbox_id uuid REFERENCES outreach_mailboxes(id),
  email text NOT NULL,
  first_name text,
  last_name text,
  company text,
  custom_fields jsonb DEFAULT '{}',
  sequence_status text NOT NULL DEFAULT 'pending',
  current_step integer NOT NULL DEFAULT 0,
  next_send_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outreach_leads_campaign ON outreach_leads (campaign_id);
CREATE INDEX IF NOT EXISTS idx_outreach_leads_next_send ON outreach_leads (sequence_status, next_send_at);

CREATE TABLE IF NOT EXISTS outreach_emails (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid NOT NULL REFERENCES outreach_leads(id) ON DELETE CASCADE,
  mailbox_id uuid REFERENCES outreach_mailboxes(id),
  step_number integer NOT NULL,
  subject text,
  body text,
  status text NOT NULL DEFAULT 'scheduled',
  sent_at timestamptz,
  gmail_message_id text,
  message_id text,
  thread_id text,
  in_reply_to text,
  "references" text[],
  error text,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outreach_emails_lead ON outreach_emails (lead_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_outreach_emails_gmail_message_id
  ON outreach_emails (gmail_message_id) WHERE gmail_message_id IS NOT NULL;
`;

async function main() {
  await client.connect();
  console.log("Creating outreach tables...");
  await client.query(SQL);

  const { rows } = await client.query(`
    SELECT table_name FROM information_schema.tables
    WHERE table_name IN ('outreach_mailboxes','outreach_suppression_list','outreach_campaigns','outreach_leads','outreach_emails')
    ORDER BY table_name
  `);
  console.log("Tables present:", rows.map((r) => r.table_name).join(", "));
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await client.end();
  });
