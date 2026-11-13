/** Read-only, redacted reconciliation ledger for an in-place migration rollback. */
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { Client } from "pg";

type Cursor = { createdAt: string; id: string };
const arg = (name: string) => process.argv.find((value) => value.startsWith(`--${name}=`))?.slice(name.length + 3);
const required = (name: string) => {
  const value = arg(name)?.trim();
  if (!value) throw new Error(`--${name}=<value> is required`);
  return value;
};
const expectedInteger = (name: string) => {
  const value = Number(required(name));
  if (!Number.isSafeInteger(value) || value < 0) throw new Error(`--${name} must be a non-negative integer`);
  return value;
};
const sha = (value: unknown) => createHash("sha256").update(String(value)).digest("hex");
const appSha = () => process.env.APP_GIT_SHA ?? process.env.VERCEL_GIT_COMMIT_SHA ?? process.env.RAILWAY_GIT_COMMIT_SHA ?? process.env.GIT_SHA;

function parseCursor(prefix: "source" | "target"): Cursor {
  const createdAt = required(`${prefix}-high-water-created-at`);
  if (!Number.isFinite(Date.parse(createdAt))) throw new Error(`--${prefix}-high-water-created-at must be an ISO timestamp`);
  return { createdAt: new Date(createdAt).toISOString(), id: required(`${prefix}-high-water-id`) };
}

function safeRunId(value: string) {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/.test(value)) throw new Error("Invalid --run-id");
  return value;
}

function webhookDisposition(status: unknown) {
  switch (status) {
    case "ok": return "ok";
    case "skipped": return "intentionally_skipped";
    case "error": return "retryable_error";
    case "dead": return "manual_review_dead_letter";
    case "processing": return "manual_review_processing";
    case null: return "manual_review_legacy_unclassified";
    default: throw new Error(`Unknown WebhookEvent processingStatus: ${String(status)}`);
  }
}

async function main() {
  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) throw new Error("DATABASE_URL is not set");
  const runId = safeRunId(required("run-id"));
  const backupId = required("backup-id");
  const expectedDatabase = required("expected-database");
  const expectedHost = required("expected-host").toLowerCase();
  const expectedSha = required("expected-app-sha");
  const expectedWebhookEvents = expectedInteger("expected-webhook-events");
  const expectedBaselineNonterminal = expectedInteger("expected-baseline-nonterminal");
  const source = parseCursor("source");
  const target = parseCursor("target");
  if (target.createdAt < source.createdAt || (target.createdAt === source.createdAt && target.id < source.id)) {
    throw new Error("Target high-water cursor must not precede source high-water cursor");
  }
  const actualSha = appSha();
  if (!actualSha || actualSha !== expectedSha) throw new Error(`Application SHA mismatch: expected ${expectedSha}, found ${actualSha ?? "unset"}`);
  const url = new URL(databaseUrl);
  if (url.hostname.toLowerCase() !== expectedHost) throw new Error(`Database host mismatch: expected ${expectedHost}, found ${url.hostname}`);

  const client = new Client({
    connectionString: databaseUrl,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
    application_name: "agentsdr-readonly-people-reconciliation-export",
  });
  await client.connect();
  try {
    await client.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL statement_timeout = '2min'");
    const identity = await client.query<{ database: string }>("SELECT current_database() AS database");
    if (identity.rows[0]?.database !== expectedDatabase) {
      throw new Error(`Database mismatch: expected ${expectedDatabase}, found ${identity.rows[0]?.database}`);
    }
    const cursorValues = [source.createdAt, source.id, target.createdAt, target.id];
    const webhookResult = await client.query<Record<string, unknown>>(`
      SELECT id, "providerEventKey", event, "accountId", "senderId", "chatId",
        "connectionId", "processingStatus", "processingAttempt", "processingStartedAt",
        "nextAttemptAt", "processedAt", "createdAt"
      FROM "WebhookEvent"
      WHERE (("createdAt", id) > ($1::timestamptz, $2::text)
          AND ("createdAt", id) <= ($3::timestamptz, $4::text))
         OR (("createdAt", id) <= ($1::timestamptz, $2::text)
          AND coalesce("processingStatus", '') NOT IN ('ok', 'skipped'))
      ORDER BY "createdAt", id
    `, cursorValues);
    const intervalWebhooks = webhookResult.rows.filter((row) => {
      const key = [new Date(String(row.createdAt)).toISOString(), String(row.id)];
      return key[0] > source.createdAt || (key[0] === source.createdAt && key[1] > source.id);
    });
    const baselineNonterminal = webhookResult.rows.length - intervalWebhooks.length;
    if (intervalWebhooks.length !== expectedWebhookEvents || baselineNonterminal !== expectedBaselineNonterminal) {
      throw new Error(`Webhook count drift: interval expected ${expectedWebhookEvents}/found ${intervalWebhooks.length}; baseline nonterminal expected ${expectedBaselineNonterminal}/found ${baselineNonterminal}`);
    }

    const timeValues = [source.createdAt, target.createdAt];
    const messages = await client.query<Record<string, unknown>>(`SELECT id, "leadId", type, "linkedinMessageId", "connectionId", "duplicateOfMessageId", "createdAt" FROM "Message" WHERE "createdAt" > $1 AND "createdAt" <= $2 ORDER BY "createdAt", id`, timeValues);
    const connections = await client.query<Record<string, unknown>>(`SELECT id, "providerId", "leadId", "linkedinAccountId", "connectedAt", "createdAt", "updatedAt" FROM "Connection" WHERE ("createdAt" > $1 OR "updatedAt" > $1) AND "createdAt" <= $2 ORDER BY "createdAt", id`, timeValues);
    // outreach_emails has no updated_at, so an interval query would miss an old
    // scheduled row becoming sent/failed/replied. Capture the complete current
    // active-campaign set for comparison with the pre-cutover snapshot.
    const emails = await client.query<Record<string, unknown>>(`
      SELECT e.id, e.lead_id, e.mailbox_id, e.step_number, e.status, e.sent_at,
        e.gmail_message_id, e.message_id, e.thread_id, e.error, e.created_at
      FROM outreach_emails e
      JOIN outreach_leads l ON l.id = e.lead_id
      JOIN outreach_campaigns c ON c.id = l.campaign_id
      WHERE c.status = 'active'
      ORDER BY e.created_at, e.id
    `);
    const linkedinLeads = await client.query<Record<string, unknown>>(`SELECT id, "personId", "campaignId", "providerId", status, "linkedinAccountId", "supersededByLeadId", "updatedAt" FROM "Lead" WHERE "updatedAt" > $1 AND "updatedAt" <= $2 ORDER BY "updatedAt", id`, timeValues);
    const emailLeads = await client.query<Record<string, unknown>>(`SELECT id, person_id, campaign_id, mailbox_id, sequence_status, current_step, next_send_at, updated_at FROM outreach_leads WHERE updated_at > $1 AND updated_at <= $2 ORDER BY updated_at, id`, timeValues);
    const queue = await client.query<Record<string, unknown>>(`SELECT id, mailbox_id, lead_id, position, created_at FROM outreach_mailbox_queue WHERE created_at > $1 AND created_at <= $2 ORDER BY created_at, id`, timeValues);
    const suppressions = await client.query<Record<string, unknown>>(`SELECT id, reason, created_at, email FROM outreach_suppression_list WHERE created_at > $1 AND created_at <= $2 ORDER BY created_at, id`, timeValues);
    const people = await client.query<Record<string, unknown>>(`SELECT id, source, updated_at, email, linkedin_url FROM people WHERE updated_at > $1 AND updated_at <= $2 ORDER BY updated_at, id`, timeValues);
    const emailWebhookEvents = await client.query<Record<string, unknown>>(`
      SELECT id, source, event_type, title, status, processed, error, created_at
      FROM crm_webhook_events
      WHERE (created_at > $1 AND created_at <= $2)
         OR (created_at <= $1 AND (processed = false OR status = 'error'))
      ORDER BY created_at, id
    `, timeValues);
    await client.query("ROLLBACK");

    const webhookEvents = webhookResult.rows.map((row) => ({
      ...row,
      providerEventKey: row.providerEventKey == null ? null : sha(row.providerEventKey),
      accountId: row.accountId == null ? null : sha(row.accountId),
      senderId: row.senderId == null ? null : sha(row.senderId),
      chatId: row.chatId == null ? null : sha(row.chatId),
      disposition: webhookDisposition(row.processingStatus),
    }));
    const report = {
      createdAt: new Date().toISOString(), runId, backupId, applicationSha: actualSha,
      database: expectedDatabase, host: expectedHost, sourceHighWater: source, targetHighWater: target,
      counts: {
        webhookEvents: intervalWebhooks.length, baselineNonterminal,
        emailWebhookEvents: emailWebhookEvents.rows.length,
        messages: messages.rows.length, connections: connections.rows.length, emails: emails.rows.length,
        linkedinLeads: linkedinLeads.rows.length, emailLeads: emailLeads.rows.length,
        queue: queue.rows.length, suppressions: suppressions.rows.length, people: people.rows.length,
      },
      webhookEvents,
      changes: {
        emailWebhookEvents: emailWebhookEvents.rows.map(({ title, ...row }) => ({
          ...row,
          titleHash: title == null ? null : sha(title),
        })),
        messages: messages.rows.map((row) => ({ ...row, linkedinMessageId: row.linkedinMessageId == null ? null : sha(row.linkedinMessageId) })),
        connections: connections.rows.map((row) => ({ ...row, providerId: sha(row.providerId) })),
        emails: emails.rows.map((row) => ({ ...row, gmail_message_id: row.gmail_message_id == null ? null : sha(row.gmail_message_id), message_id: row.message_id == null ? null : sha(row.message_id), thread_id: row.thread_id == null ? null : sha(row.thread_id) })),
        linkedinLeads: linkedinLeads.rows.map((row) => ({ ...row, providerId: row.providerId == null ? null : sha(row.providerId) })),
        emailLeads: emailLeads.rows,
        queue: queue.rows,
        suppressions: suppressions.rows.map(({ email, ...row }) => ({ ...row, emailHash: sha(String(email).toLowerCase()) })),
        people: people.rows.map(({ email, linkedin_url: linkedinUrl, ...row }) => ({
          ...row,
          emailHash: email == null ? null : sha(String(email).toLowerCase()),
          linkedinHash: linkedinUrl == null ? null : sha(linkedinUrl),
        })),
      },
      limitations: ["updated-state tables are current snapshots, not row-level pre-images", "deleted queue rows require comparison with the pre-cutover snapshot", "provider truth must be reconciled separately before any worker resumes"],
    };
    const directory = resolve("reports/migration/reconciliation");
    await mkdir(directory, { recursive: true, mode: 0o700 });
    const reportPath = resolve(directory, `${runId}.json`);
    await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, { encoding: "utf8", mode: 0o600, flag: "wx" });
    console.log(JSON.stringify({ passed: true, reportPath, counts: report.counts }, null, 2));
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
