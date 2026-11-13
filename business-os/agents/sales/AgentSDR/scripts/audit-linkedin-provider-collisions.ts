/** Read-only audit for ambiguous LinkedIn provider/account ownership. */
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { Client } from "pg";

const TERMINAL = new Set(["COMPLETED", "REPLIED", "FAILED", "CANCELLED"]);
const hash = (value: string) => createHash("sha256").update(value).digest("hex");

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const client = new Client({ connectionString: process.env.DATABASE_URL, ssl: { rejectUnauthorized: false }, application_name: "agentsdr-readonly-provider-collision-audit" });
  await client.connect();
  try {
    await client.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL statement_timeout = '30s'");
    const { rows: supersededColumnRows } = await client.query<{ present: boolean }>(`
      SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'Lead' AND column_name = 'supersededByLeadId'
      ) AS present
    `);
    const canonicalPredicate = supersededColumnRows[0]?.present ? `AND "supersededByLeadId" IS NULL` : "";
    const { rows } = await client.query<{
      id: string; providerId: string; linkedinAccountId: string; status: string;
      campaignId: string | null; campaignStatus: string | null; linkedinUrl: string | null;
      messageCount: number; connectionCount: number;
    }>(`
      WITH collisions AS (
        SELECT "providerId", "linkedinAccountId"
        FROM "Lead"
        WHERE "providerId" IS NOT NULL AND "linkedinAccountId" IS NOT NULL
          ${canonicalPredicate}
        GROUP BY "providerId", "linkedinAccountId"
        HAVING count(*) > 1
      )
      SELECT l.id, l."providerId", l."linkedinAccountId", l.status, l."campaignId",
        c.status AS "campaignStatus", l."linkedinUrl",
        (SELECT count(*)::int FROM "Message" m WHERE m."leadId" = l.id) AS "messageCount",
        (SELECT count(*)::int FROM "Connection" x WHERE x."leadId" = l.id) AS "connectionCount"
      FROM collisions d
      JOIN "Lead" l ON l."providerId" = d."providerId" AND l."linkedinAccountId" = d."linkedinAccountId"
      LEFT JOIN "Campaign" c ON c.id = l."campaignId"
      ORDER BY l."providerId", l."linkedinAccountId", l."createdAt", l.id
    `);
    await client.query("ROLLBACK");

    const grouped = new Map<string, typeof rows>();
    for (const row of rows) {
      const key = `${row.providerId}\u0000${row.linkedinAccountId}`;
      const group = grouped.get(key) ?? [];
      group.push(row);
      grouped.set(key, group);
    }
    const groups = [...grouped.values()].map((members) => ({
      providerHash: hash(members[0].providerId),
      accountHash: hash(members[0].linkedinAccountId),
      actionableRows: members.filter((row) => row.campaignStatus === "ACTIVE" && !TERMINAL.has(row.status)).length,
      members: members.map((row) => ({
        leadId: row.id,
        campaignId: row.campaignId,
        campaignStatus: row.campaignStatus,
        status: row.status,
        linkedinIdentityHash: row.linkedinUrl ? hash(row.linkedinUrl.trim().toLowerCase()) : null,
        messageCount: row.messageCount,
        connectionCount: row.connectionCount,
      })),
    }));
    const summary = {
      auditedAt: new Date().toISOString(),
      readOnly: true,
      collisionGroups: groups.length,
      groupsWithMultipleActionableRows: groups.filter((group) => group.actionableRows > 1).length,
      actionableRows: groups.reduce((total, group) => total + group.actionableRows, 0),
    };
    const reportPath = resolve("reports/migration/linkedin-provider-collisions.json");
    await mkdir(resolve("reports/migration"), { recursive: true });
    await writeFile(reportPath, `${JSON.stringify({ summary, groups }, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify(summary, null, 2));
    console.log(`Redacted report written to ${reportPath}`);
    if (summary.groupsWithMultipleActionableRows) process.exitCode = 2;
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
