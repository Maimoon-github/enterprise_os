/**
 * Read-only old-vs-People LinkedIn behavior comparison.
 *
 * This intentionally requires a separately named URL so Bun cannot silently
 * use the repository's production `.env.local` value:
 *   LINKEDIN_PARITY_DATABASE_URL=... LINKEDIN_PARITY_EXPECTED_DATABASE=... \
 *     bun --no-env-file --conditions=react-server scripts/audit-linkedin-migration-parity.ts
 */
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { Client } from "pg";
import { personVariables } from "../src/lib/leads/variables";
import {
  classifyWebhookOwnership,
  compareEligibleAccountIds,
  compareLinkedinLead,
  type LinkedinParityLead,
} from "../src/lib/linkedin/migrationParity";

const REPORT = resolve("reports/migration/linkedin-behavior-parity.json");
const hash = (value: unknown) => createHash("sha256").update(JSON.stringify(value)).digest("hex");

type DbRow = {
  id: string;
  status: string;
  campaignStatus: string | null;
  campaignId: string | null;
  personId: string | null;
  providerId: string | null;
  linkedinAccountId: string | null;
  legacyLinkedinUrl: string | null;
  personLinkedinUrl: string | null;
  sourceLinkedinIdentifier: string | null;
  sourceLinkedinApi: string | null;
  inviteRetryCount: number;
  resolveRetryCount: number;
  resolveNextAttemptAt: Date | null;
  requestSentAt: Date | null;
  acceptMessageSentAt: Date | null;
  followUp1SentAt: Date | null;
  followUp2SentAt: Date | null;
  createdAt: Date;
  supersededByLeadId: string | null;
  connectionChatId: string | null;
  leadTemplates: Record<string, string | null>;
  campaignTemplates: Record<string, string | null>;
  canonicalMessageTypes: string[];
  personEmail: string | null;
  personFirstName: string | null;
  personLastName: string | null;
  personFullName: string | null;
  personTitle: string | null;
  personRaw: Record<string, unknown> | null;
  companyDomain: string | null;
  companyName: string | null;
  companyLinkedinUrl: string | null;
  companyRaw: Record<string, unknown> | null;
};

async function main() {
  const connectionString = process.env.LINKEDIN_PARITY_DATABASE_URL;
  const expectedDatabase = process.env.LINKEDIN_PARITY_EXPECTED_DATABASE;
  if (!connectionString || !expectedDatabase) {
    throw new Error("Set LINKEDIN_PARITY_DATABASE_URL and LINKEDIN_PARITY_EXPECTED_DATABASE explicitly; DATABASE_URL is deliberately ignored");
  }
  const client = new Client({
    connectionString,
    ssl: process.env.LINKEDIN_PARITY_DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
    application_name: "agentsdr-readonly-linkedin-migration-parity",
  });
  await client.connect();
  try {
    await client.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL statement_timeout = '90s'");
    await client.query("SET LOCAL lock_timeout = '2s'");
    const { rows: identity } = await client.query<{ database: string }>("SELECT current_database() AS database");
    if (identity[0]?.database !== expectedDatabase) {
      throw new Error(`Database guard failed: expected ${expectedDatabase}, got ${identity[0]?.database ?? "unknown"}`);
    }

    const { rows } = await client.query<DbRow>(`
      SELECT l.id, l.status, l."campaignId", c.status AS "campaignStatus",
        l."personId", l."providerId", l."linkedinAccountId",
        l."linkedinUrl" AS "legacyLinkedinUrl", p.linkedin_url AS "personLinkedinUrl",
        l."sourceLinkedinIdentifier", l."sourceLinkedinApi",
        l."inviteRetryCount", l."resolveRetryCount", l."resolveNextAttemptAt",
        l."requestSentAt", l."acceptMessageSentAt", l."followUp1SentAt", l."followUp2SentAt",
        l."createdAt", l."supersededByLeadId",
        connection.chat_id AS "connectionChatId",
        jsonb_build_object(
          'invitationMessage', l."invitationMessage", 'acceptanceMessage', l."acceptanceMessage",
          'followUp1Message', l."followUp1Message", 'followUp2Message', l."followUp2Message",
          'followUp3Message', l."followUp3Message"
        ) AS "leadTemplates",
        jsonb_build_object(
          'invitationMessage', c."invitationMessage", 'acceptanceMessage', c."acceptanceMessage",
          'followUp1Message', c."followUp1Message", 'followUp2Message', c."followUp2Message",
          'followUp3Message', c."followUp3Message"
        ) AS "campaignTemplates",
        coalesce(message.types, ARRAY[]::text[]) AS "canonicalMessageTypes",
        p.email AS "personEmail", p.first_name AS "personFirstName", p.last_name AS "personLastName",
        p.full_name AS "personFullName", p.title AS "personTitle", p.raw AS "personRaw",
        company.domain AS "companyDomain", company.name AS "companyName",
        company.linkedin_url AS "companyLinkedinUrl", company.raw AS "companyRaw"
      FROM "Lead" l
      JOIN "Campaign" c ON c.id = l."campaignId"
      LEFT JOIN people p ON p.id = l."personId"
      LEFT JOIN companies company ON company.id = p.company_id
      LEFT JOIN LATERAL (
        SELECT x."chatId" AS chat_id FROM "Connection" x
        WHERE x."leadId" = l.id ORDER BY x."updatedAt" DESC, x.id DESC LIMIT 1
      ) connection ON true
      LEFT JOIN LATERAL (
        SELECT array_agg(DISTINCT m.type::text) AS types FROM "Message" m
        WHERE m."leadId" = l.id AND m."duplicateOfMessageId" IS NULL
      ) message ON true
      WHERE c.status = 'ACTIVE'
      ORDER BY l.id
    `);
    const { rows: connectedAccounts } = await client.query<{ id: string }>(`
      SELECT id FROM "LinkedInAccount" WHERE status = 'CONNECTED' AND "limitReached" = false ORDER BY id
    `);
    const { rows: assignments } = await client.query<{ campaignId: string; accountId: string }>(`
      SELECT "campaignId", "linkedinAccountId" AS "accountId" FROM "CampaignAccount" ORDER BY 1, 2
    `);
    const { rows: contacted } = await client.query<{ accountId: string; legacyLinkedinUrl: string; personId: string }>(`
      SELECT "linkedinAccountId" AS "accountId", lower("linkedinUrl") AS "legacyLinkedinUrl", "personId"
      FROM "Lead" WHERE "linkedinAccountId" IS NOT NULL AND status <> 'PENDING'
    `);
    const { rows: duplicateProviderMessages } = await client.query<{ providerMessageId: string; count: number }>(`
      SELECT "linkedinMessageId" AS "providerMessageId", count(*)::int AS count
      FROM "Message" WHERE "linkedinMessageId" IS NOT NULL
      GROUP BY "linkedinMessageId" HAVING count(*) > 1
    `);
    const { rows: canonicalDuplicates } = await client.query<{ count: number }>(`
      SELECT count(*)::int AS count FROM (
        SELECT "leadId", type FROM "Message"
        WHERE "leadId" IS NOT NULL
          AND "duplicateOfMessageId" IS NULL
          AND type IN ('INVITATION','ACCEPTANCE','FOLLOW_UP_1','FOLLOW_UP_2','FOLLOW_UP_3')
        GROUP BY "leadId", type HAVING count(*) > 1
      ) duplicate
    `);
    const { rows: webhookColumns } = await client.query<{ columnName: string }>(`
      SELECT column_name AS "columnName" FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'WebhookEvent'
    `);
    const { rows: webhookUniqueIndexes } = await client.query<{ definition: string }>(`
      SELECT pg_get_indexdef(indexrelid) AS definition
      FROM pg_index i JOIN pg_class c ON c.oid = i.indrelid
      WHERE c.relname = 'WebhookEvent' AND i.indisunique
    `);
    await client.query("ROLLBACK");

    const assignmentMap = new Map<string, string[]>();
    for (const row of assignments) assignmentMap.set(row.campaignId, [...(assignmentMap.get(row.campaignId) ?? []), row.accountId]);
    const legacyExcluded = new Map<string, Set<string>>();
    const peopleExcluded = new Map<string, Set<string>>();
    for (const row of contacted) {
      const oldSet = legacyExcluded.get(row.legacyLinkedinUrl) ?? new Set<string>();
      oldSet.add(row.accountId);
      legacyExcluded.set(row.legacyLinkedinUrl, oldSet);
      const newSet = peopleExcluded.get(row.personId) ?? new Set<string>();
      newSet.add(row.accountId);
      peopleExcluded.set(row.personId, newSet);
    }
    const allAccounts = connectedAccounts.map((row) => row.id);
    const now = new Date();
    const comparisons = rows.map((row) => {
      const variables = personVariables({
        email: row.personEmail,
        linkedinUrl: row.personLinkedinUrl,
        firstName: row.personFirstName,
        lastName: row.personLastName,
        fullName: row.personFullName,
        title: row.personTitle,
        raw: row.personRaw,
      }, row.companyDomain ? {
        domain: row.companyDomain,
        name: row.companyName,
        linkedinUrl: row.companyLinkedinUrl,
        raw: row.companyRaw,
      } : null);
      const input: LinkedinParityLead = { ...row, variables, canonicalMessageTypes: new Set(row.canonicalMessageTypes) };
      const comparison = compareLinkedinLead(input, now);
      const candidates = assignmentMap.get(row.campaignId ?? "") ?? allAccounts;
      const accounts = compareEligibleAccountIds(
        candidates,
        legacyExcluded.get(row.legacyLinkedinUrl?.toLowerCase() ?? "") ?? new Set(),
        peopleExcluded.get(row.personId ?? "") ?? new Set(),
      );
      const accountSelectionUnsafe = row.status === "PENDING" && !accounts.safeNarrowing;
      return {
        leadId: row.id,
        differences: [...comparison.differences, ...(accountSelectionUnsafe ? ["eligible_accounts"] : [])],
        safeAccountNarrowing: row.status === "PENDING" && !accounts.matches && accounts.safeNarrowing,
        target: {
          usable: comparison.targetCompatible,
          providerHash: row.providerId ? hash(row.providerId) : null,
          sourceHash: row.sourceLinkedinIdentifier ? hash(row.sourceLinkedinIdentifier) : null,
          oldSlugHash: comparison.oldSlug ? hash(comparison.oldSlug) : null,
          newSlugHash: comparison.newSlug ? hash(comparison.newSlug) : null,
        },
        assignedAccountHash: row.linkedinAccountId ? hash(row.linkedinAccountId) : null,
        eligibleAccountHashes: { legacy: accounts.legacy.map(hash), current: accounts.current.map(hash) },
        actions: {
          legacy: { ...comparison.legacy, template: comparison.legacy.template ? hash(comparison.legacy.template) : null, rendered: comparison.legacy.rendered ? hash(comparison.legacy.rendered) : null },
          current: { ...comparison.current, template: comparison.current.template ? hash(comparison.current.template) : null, rendered: comparison.current.rendered ? hash(comparison.current.rendered) : null },
        },
      };
    });

    const providerGroups = new Map<string, typeof rows>();
    for (const row of rows) {
      if (!row.providerId || !row.linkedinAccountId) continue;
      const key = `${row.providerId}\u0000${row.linkedinAccountId}`;
      providerGroups.set(key, [...(providerGroups.get(key) ?? []), row]);
    }
    const webhookOwnership = [...providerGroups.entries()].map(([key, members]) => {
      const ownership = classifyWebhookOwnership(members.map((row) => ({
        id: row.id,
        status: row.status,
        superseded: Boolean(row.supersededByLeadId),
        requestSentAt: row.requestSentAt,
        createdAt: row.createdAt,
      })));
      return { keyHash: hash(key), leadIds: members.map((row) => row.id), ...ownership };
    });
    const webhookProviderEventIdPresent = webhookColumns.some((row) => /provider.*event.*(?:id|key)/i.test(row.columnName));
    const webhookProviderEventIdUnique = webhookUniqueIndexes.some((row) => /provider.*event.*(?:id|key)/i.test(row.definition));
    const blockers = {
      leadParityDifferences: comparisons.filter((row) => row.differences.length > 0).length,
      ambiguousInboundOwnership: webhookOwnership.filter((row) => row.inboundAmbiguous).length,
      ambiguousConnectionOwnership: webhookOwnership.filter((row) => row.connectionAmbiguous).length,
      duplicateProviderMessageIds: duplicateProviderMessages.length,
      duplicateCanonicalAutomatedSteps: Number(canonicalDuplicates[0]?.count ?? 0),
      missingDurableWebhookEventIdentity: webhookProviderEventIdPresent && webhookProviderEventIdUnique ? 0 : 1,
    };
    const report = {
      checkedAt: now.toISOString(),
      mode: "read-only",
      database: identity[0]?.database,
      passed: Object.values(blockers).every((count) => count === 0),
      blockers,
      comparisons,
      webhookOwnership,
      duplicateProviderMessageIds: duplicateProviderMessages.map((row) => ({ providerMessageHash: hash(row.providerMessageId), count: row.count })),
    };
    await mkdir(resolve("reports/migration"), { recursive: true });
    await writeFile(REPORT, `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify({ ...report, comparisons: undefined, webhookOwnership: undefined, duplicateProviderMessageIds: undefined }, null, 2));
    console.log(`Redacted detail written to ${REPORT}`);
    if (!report.passed) process.exitCode = 2;
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
