/** Read-only post-migration invariant checker. Exits non-zero on any blocker. */
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { Client } from "pg";

const CHECKS = [
  ["email_leads_without_person", `SELECT count(*)::int AS count FROM outreach_leads WHERE person_id IS NULL`],
  ["linkedin_leads_without_person", `SELECT count(*)::int AS count FROM "Lead" WHERE "personId" IS NULL`],
  ["email_leads_without_person_email", `
    SELECT count(*)::int AS count FROM outreach_leads l
    LEFT JOIN people p ON p.id = l.person_id WHERE p.id IS NULL OR p.email IS NULL
  `],
  ["actionable_linkedin_without_provider_target", `
    SELECT count(*)::int AS count FROM "Lead" l LEFT JOIN people p ON p.id = l."personId"
    WHERE l.status IN ('REQUEST_SENT', 'CONNECTED', 'ACCEPT_MESSAGE_SENT', 'FOLLOW_UP_1_SENT', 'FOLLOW_UP_2_SENT', 'FOLLOW_UP_3_SENT')
      AND (p.id IS NULL OR l."providerId" IS NULL)
  `],
  ["pending_linkedin_without_resolution_path", `
    SELECT count(*)::int AS count FROM "Lead" l LEFT JOIN people p ON p.id = l."personId"
    WHERE l.status = 'PENDING' AND (
      p.id IS NULL OR ((p.linkedin_url IS NULL OR l."providerId" IS NULL) AND l."sourceLinkedinIdentifier" IS NULL)
    )
  `],
  ["duplicate_email_memberships", `SELECT count(*)::int AS count FROM (
    SELECT person_id, campaign_id FROM outreach_leads GROUP BY person_id, campaign_id HAVING count(*) > 1
  ) duplicate`],
  ["duplicate_email_queue_memberships", `SELECT count(*)::int AS count FROM (
    SELECT lead_id FROM outreach_mailbox_queue GROUP BY lead_id HAVING count(*) > 1
  ) duplicate`],
  ["duplicate_email_step_attempts", `SELECT count(*)::int AS count FROM (
    SELECT lead_id, step_number FROM outreach_emails GROUP BY lead_id, step_number HAVING count(*) > 1
  ) duplicate`],
  ["duplicate_inbound_email_provider_ids", `SELECT count(*)::int AS count FROM (
    SELECT smartlead_message_id FROM crm_messages WHERE smartlead_message_id IS NOT NULL
    GROUP BY smartlead_message_id HAVING count(*) > 1
  ) duplicate`],
  ["duplicate_linkedin_memberships", `SELECT count(*)::int AS count FROM (
    SELECT "personId", "campaignId" FROM "Lead" WHERE "campaignId" IS NOT NULL
    GROUP BY "personId", "campaignId" HAVING count(*) > 1
  ) duplicate`],
  ["duplicate_canonical_automated_messages", `SELECT count(*)::int AS count FROM (
    SELECT "leadId", type FROM "Message"
    WHERE "leadId" IS NOT NULL AND "duplicateOfMessageId" IS NULL
      AND type IN ('INVITATION', 'ACCEPTANCE', 'FOLLOW_UP_1', 'FOLLOW_UP_2', 'FOLLOW_UP_3')
    GROUP BY "leadId", type HAVING count(*) > 1
  ) duplicate`],
  ["orphaned_historical_message_duplicates", `
    SELECT count(*)::int AS count FROM "Message" d LEFT JOIN "Message" c ON c.id = d."duplicateOfMessageId"
    WHERE d."duplicateOfMessageId" IS NOT NULL AND (c.id IS NULL OR c."duplicateOfMessageId" IS NOT NULL)
  `],
  ["active_superseded_linkedin_leads", `
    SELECT count(*)::int AS count FROM "Lead"
    WHERE "supersededByLeadId" IS NOT NULL AND status <> 'CANCELLED'
  `],
  ["ambiguous_actionable_provider_ownership", `SELECT count(*)::int AS count FROM (
    SELECT "providerId", "linkedinAccountId" FROM "Lead"
    WHERE "providerId" IS NOT NULL AND "linkedinAccountId" IS NOT NULL
      AND "supersededByLeadId" IS NULL
      AND status NOT IN ('COMPLETED', 'REPLIED', 'FAILED', 'CANCELLED')
    GROUP BY "providerId", "linkedinAccountId" HAVING count(*) > 1
  ) collision`],
] as const;

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const client = new Client({ connectionString: process.env.DATABASE_URL, ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false }, application_name: "agentsdr-readonly-people-postflight" });
  await client.connect();
  try {
    await client.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL statement_timeout = '60s'");
    const results: Record<string, number> = {};
    for (const [name, sql] of CHECKS) {
      const { rows } = await client.query<{ count: number }>(sql);
      results[name] = Number(rows[0]?.count ?? 0);
    }
    const { rows: totals } = await client.query<{ emailLeads: number; linkedinLeads: number; people: number; messages: number }>(`
      SELECT
        (SELECT count(*)::int FROM outreach_leads) AS "emailLeads",
        (SELECT count(*)::int FROM "Lead") AS "linkedinLeads",
        (SELECT count(*)::int FROM people) AS people,
        (SELECT count(*)::int FROM "Message") AS messages
    `);
    await client.query("ROLLBACK");
    const blockers = Object.entries(results).filter(([, count]) => count !== 0);
    const report = { checkedAt: new Date().toISOString(), readOnly: true, passed: blockers.length === 0, totals: totals[0], checks: results };
    const reportPath = resolve("reports/migration/postflight-latest.json");
    await mkdir(resolve("reports/migration"), { recursive: true });
    await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify(report, null, 2));
    if (blockers.length) process.exitCode = 2;
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
