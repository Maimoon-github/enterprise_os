/**
 * Captures a redacted, deterministic baseline of active Email and LinkedIn
 * outreach. Run before migration with --write-baseline and after migration
 * without it. Database access is always read-only.
 */
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { Client } from "pg";

const BASELINE = resolve("reports/migration/active-outreach-baseline.json");
const hash = (value: unknown) => createHash("sha256").update(JSON.stringify(value)).digest("hex");
const hashNullable = (value: unknown) => value === null || value === undefined ? null : hash(value);

function fingerprints(rows: Array<Record<string, unknown>>) {
  return Object.fromEntries(rows.map((row) => [String(row.id), hash(row)]));
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const writeBaseline = process.argv.includes("--write-baseline");
  const client = new Client({ connectionString: process.env.DATABASE_URL, ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false }, application_name: "agentsdr-readonly-active-outreach-snapshot" });
  await client.connect();
  try {
    await client.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL statement_timeout = '60s'");
    const { rows: emailLeads } = await client.query<Record<string, unknown>>(`
      SELECT l.id, l.campaign_id, lower(l.email) AS recipient,
        l.sequence_status, l.current_step, l.next_send_at, l.mailbox_id,
        l.custom_fields AS variables, c.status AS campaign_status, c.sequence
      FROM outreach_leads l JOIN outreach_campaigns c ON c.id = l.campaign_id
      WHERE c.status = 'active' ORDER BY l.id
    `);
    const { rows: linkedinLeads } = await client.query<Record<string, unknown>>(`
      SELECT l.id, l."campaignId", lower(l."linkedinUrl") AS recipient,
        l."providerId", l.status, l."inviteRetryCount", l."requestSentAt", l."acceptMessageSentAt",
        l."followUp1SentAt", l."followUp2SentAt", l."followUp3SentAt", l."linkedinAccountId",
        c.status AS campaign_status
      FROM "Lead" l JOIN "Campaign" c ON c.id = l."campaignId"
      WHERE c.status = 'ACTIVE' ORDER BY l.id
    `);
    const { rows: emailMessages } = await client.query<Record<string, unknown>>(`
      SELECT e.id, e.lead_id, e.step_number, e.status, e.sent_at, e.gmail_message_id,
        e.message_id, e.thread_id, e.subject, e.body
      FROM outreach_emails e JOIN outreach_leads l ON l.id = e.lead_id
      JOIN outreach_campaigns c ON c.id = l.campaign_id WHERE c.status = 'active' ORDER BY e.id
    `);
    const { rows: linkedinMessages } = await client.query<Record<string, unknown>>(`
      SELECT m.id, m."leadId", m.type, m."linkedinMessageId", m."connectionId", m."createdAt",
        m.text
      FROM "Message" m JOIN "Lead" l ON l.id = m."leadId"
      JOIN "Campaign" c ON c.id = l."campaignId" WHERE c.status = 'ACTIVE' ORDER BY m.id
    `);
    await client.query("ROLLBACK");

    const redactRows = (rows: Array<Record<string, unknown>>, sensitiveKeys: string[]) => rows.map((row) => ({
      ...row,
      ...Object.fromEntries(sensitiveKeys.map((key) => [key, hashNullable(row[key])])),
    }));
    const redactedEmailLeads = redactRows(emailLeads, ["recipient", "variables", "sequence"]);
    const redactedLinkedinLeads = redactRows(linkedinLeads, ["recipient"]);
    const redactedEmailMessages = redactRows(emailMessages, ["subject", "body"]);
    const redactedLinkedinMessages = redactRows(linkedinMessages, ["text"]);
    const snapshot = {
      capturedAt: new Date().toISOString(),
      counts: {
        emailLeads: emailLeads.length,
        linkedinLeads: linkedinLeads.length,
        emailMessages: emailMessages.length,
        linkedinMessages: linkedinMessages.length,
      },
      fingerprints: {
        emailLeads: fingerprints(redactedEmailLeads),
        linkedinLeads: fingerprints(redactedLinkedinLeads),
        emailMessages: fingerprints(redactedEmailMessages),
        linkedinMessages: fingerprints(redactedLinkedinMessages),
      },
    };
    await mkdir(resolve("reports/migration"), { recursive: true });
    if (writeBaseline) {
      await writeFile(BASELINE, `${JSON.stringify(snapshot, null, 2)}\n`, { mode: 0o600 });
      console.log(JSON.stringify({ mode: "baseline-written", path: BASELINE, counts: snapshot.counts }, null, 2));
      return;
    }

    const baseline = JSON.parse(await readFile(BASELINE, "utf8")) as typeof snapshot;
    const changed: Record<string, string[]> = {};
    for (const key of Object.keys(snapshot.fingerprints) as Array<keyof typeof snapshot.fingerprints>) {
      const before = baseline.fingerprints[key];
      const after = snapshot.fingerprints[key];
      changed[key] = [...new Set([...Object.keys(before), ...Object.keys(after)])]
        .filter((id) => before[id] !== after[id]);
    }
    const passed = Object.values(changed).every((ids) => ids.length === 0);
    console.log(JSON.stringify({ mode: "compare", passed, baselineAt: baseline.capturedAt, counts: snapshot.counts, changed }, null, 2));
    if (!passed) process.exitCode = 2;
  } catch (error) {
    try { await client.query("ROLLBACK"); } catch { /* connection may already be closed */ }
    throw error;
  } finally {
    await client.end();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
