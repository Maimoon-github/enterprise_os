/** Read-only classifier for legacy LinkedIn identifiers before People backfill. */
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "pg";
import { normalizeLinkedinSlug } from "../src/lib/leads/identity";

type Classification = "public_url" | "sales_navigator" | "recruiter" | "provider_id" | "encoded" | "public_slug" | "opaque";

function hash(value: string) {
  return createHash("sha256").update(value).digest("hex");
}

export function classifyLinkedinIdentifier(value: string): Classification {
  const trimmed = value.trim();
  const lower = trimmed.toLowerCase();
  if (/linkedin\.com\/in\//i.test(trimmed)) return "public_url";
  if (lower.includes("sales.linkedin.com") || lower.includes("/sales/")) return "sales_navigator";
  if (lower.includes("recruiter.linkedin.com") || lower.includes("/talent/")) return "recruiter";
  if (/^aco[a-z0-9_-]+$/i.test(trimmed)) return "provider_id";
  if (/%[0-9a-f]{2}/i.test(trimmed)) return "encoded";
  if (/^[\p{L}\p{N}][\p{L}\p{N}._-]*$/u.test(trimmed)) return "public_slug";
  return "opaque";
}

function canonicalFromLeadData(value: unknown) {
  const raw = value && typeof value === "object" ? value as Record<string, unknown> : {};
  for (const candidate of [raw.public_identifier, raw.public_profile_url]) {
    if (typeof candidate !== "string") continue;
    const canonical = normalizeLinkedinSlug(candidate);
    if (canonical) return canonical;
  }
  return null;
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
    application_name: "agentsdr-readonly-legacy-linkedin-identifier-audit",
  });
  await client.connect();
  try {
    await client.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL statement_timeout = '30s'");
    const { rows } = await client.query<{
      id: string; linkedinUrl: string | null; providerId: string | null; leadData: unknown;
      status: string; campaignId: string | null; campaignStatus: string | null;
    }>(`
      SELECT l.id, l."linkedinUrl", l."providerId", l."leadData", l.status,
        l."campaignId", c.status AS "campaignStatus"
      FROM "Lead" l LEFT JOIN "Campaign" c ON c.id = l."campaignId"
    `);
    await client.query("ROLLBACK");

    const unresolved = rows.flatMap((row) => {
      if (canonicalFromLeadData(row.leadData) || !row.linkedinUrl?.trim()) return [];
      const classification = classifyLinkedinIdentifier(row.linkedinUrl);
      return [{
        leadId: row.id,
        campaignId: row.campaignId,
        campaignStatus: row.campaignStatus,
        leadStatus: row.status,
        sourceHash: hash(row.linkedinUrl.trim()),
        classification,
        hasProviderId: Boolean(row.providerId),
        actionable: row.campaignStatus === "ACTIVE" && row.status === "PENDING",
        recommendedSource: row.providerId ? "provider_id" : classification,
      }];
    });
    const summary = {
      auditedAt: new Date().toISOString(),
      readOnly: true,
      unresolvedRows: unresolved.length,
      actionableRows: unresolved.filter((row) => row.actionable).length,
      withProviderId: unresolved.filter((row) => row.hasProviderId).length,
      byClassification: Object.fromEntries(
        [...new Set(unresolved.map((row) => row.classification))].sort().map((classification) => [
          classification,
          unresolved.filter((row) => row.classification === classification).length,
        ]),
      ),
    };
    const reportPath = resolve("reports/migration/legacy-linkedin-identifiers.json");
    await mkdir(resolve("reports/migration"), { recursive: true });
    await writeFile(reportPath, `${JSON.stringify({ summary, unresolved }, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify(summary, null, 2));
    console.log(`Redacted report written to ${reportPath}`);
    if (process.argv.includes("--require-actionable-resolved") && summary.actionableRows > 0) {
      console.error("Migration blocked: active campaigns still contain unresolved LinkedIn identifiers.");
      process.exitCode = 2;
    }
  } catch (error) {
    try { await client.query("ROLLBACK"); } catch { /* connection may already be closed */ }
    throw error;
  } finally {
    await client.end();
  }
}

if (resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
