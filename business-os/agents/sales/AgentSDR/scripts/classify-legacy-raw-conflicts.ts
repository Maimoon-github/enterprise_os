/**
 * Read-only classifier for legacy campaign values that would collapse into the
 * same Person.raw key during backfill. Production values are represented by
 * hashes in the report; no Email address or raw value is written to disk.
 *
 * Run with: bun --conditions=react-server scripts/classify-legacy-raw-conflicts.ts
 */
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { Client } from "pg";
import { legacyPersonIdentityKey, normalizeEmail, normalizeLinkedinSlug } from "../src/lib/leads/identity";
import { stripLegacyIdentityFields } from "../src/lib/leads/legacyRaw";

type SourceValue = {
  channel: "email" | "linkedin";
  rowId: string;
  campaignId: string | null;
  active: boolean;
  referenced: boolean;
  valueHash: string;
};

const TOKEN = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;

function hash(value: string) {
  return createHash("sha256").update(value).digest("hex");
}

function stableValue(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableValue).join(",")}]`;
  return `{${Object.entries(value as Record<string, unknown>)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, item]) => `${JSON.stringify(key)}:${stableValue(item)}`)
    .join(",")}}`;
}

function nonEmpty(value: unknown) {
  return value !== null && value !== undefined && value !== "";
}

function templateTokens(...templates: unknown[]) {
  const tokens = new Set<string>();
  for (const template of templates) {
    if (typeof template !== "string") continue;
    for (const match of template.matchAll(TOKEN)) tokens.add(match[1].toLowerCase());
  }
  return tokens;
}

function emailFromLeadData(value: unknown): string | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  if (typeof raw.email === "string") {
    const normalized = normalizeEmail(raw.email);
    if (normalized) return normalized;
  }
  const contact = raw.contact_info && typeof raw.contact_info === "object"
    ? raw.contact_info as Record<string, unknown>
    : null;
  for (const item of Array.isArray(contact?.emails) ? contact.emails : []) {
    const candidate = typeof item === "string"
      ? item
      : item && typeof item === "object"
        ? ((item as Record<string, unknown>).email ?? (item as Record<string, unknown>).value)
        : null;
    if (typeof candidate === "string") {
      const normalized = normalizeEmail(candidate);
      if (normalized) return normalized;
    }
  }
  return null;
}

function linkedinFromLeadData(value: unknown): string | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  for (const candidate of [raw.public_identifier, raw.public_profile_url]) {
    if (typeof candidate !== "string") continue;
    const normalized = normalizeLinkedinSlug(candidate);
    if (normalized) return normalized;
  }
  return null;
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
    application_name: "agentsdr-readonly-legacy-raw-conflict-audit",
  });
  await client.connect();
  try {
    await client.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL statement_timeout = '60s'");
    await client.query("SET LOCAL lock_timeout = '2s'");

    const { rows: campaignTemplateColumnRows } = await client.query<{ count: number }>(`
      SELECT count(*)::int AS count
      FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'Campaign'
        AND column_name IN ('invitationMessage', 'acceptanceMessage', 'followUp1Message', 'followUp2Message', 'followUp3Message')
    `);
    const hasCampaignTemplates = Number(campaignTemplateColumnRows[0]?.count ?? 0) === 5;
    const campaignTemplatesSql = hasCampaignTemplates
      ? `ARRAY[c."invitationMessage", c."acceptanceMessage", c."followUp1Message", c."followUp2Message", c."followUp3Message"]`
      : `ARRAY[]::text[]`;

    const { rows: emailRows } = await client.query<{
        id: string; campaignId: string; email: string | null; firstName: string | null;
        lastName: string | null; company: string | null; customFields: Record<string, unknown> | null;
        campaignStatus: string; sequence: Array<{ subject?: string; body?: string }> | null;
      }>(`
        SELECT l.id, l.campaign_id AS "campaignId", l.email, l.first_name AS "firstName",
          l.last_name AS "lastName", l.company, l.custom_fields AS "customFields",
          c.status AS "campaignStatus", c.sequence
        FROM outreach_leads l
        JOIN outreach_campaigns c ON c.id = l.campaign_id
      `);
    const { rows: linkedinRows } = await client.query<{
          id: string; campaignId: string | null; leadData: Record<string, unknown> | null;
        name: string | null; headline: string | null; location: string | null;
        profilePictureUrl: string | null; campaignStatus: string | null;
        campaignTemplates: Array<string | null>; leadTemplates: Array<string | null>;
      }>(`
        SELECT l.id, l."campaignId", l."leadData", l.name, l.headline, l.location,
          l."profilePictureUrl", c.status AS "campaignStatus",
          ${campaignTemplatesSql} AS "campaignTemplates",
          ARRAY[l."invitationMessage", l."acceptanceMessage", l."followUp1Message", l."followUp2Message", l."followUp3Message"] AS "leadTemplates"
        FROM "Lead" l
        LEFT JOIN "Campaign" c ON c.id = l."campaignId"
      `);
    await client.query("ROLLBACK");

    const valuesByIdentityAndKey = new Map<string, SourceValue[]>();
    const add = (identity: string, key: string, value: unknown, source: Omit<SourceValue, "referenced" | "valueHash">, tokens: Set<string>) => {
      if (!nonEmpty(value)) return;
      const normalizedKey = key.toLowerCase();
      const mapKey = `${identity}\u0000${normalizedKey}`;
      const values = valuesByIdentityAndKey.get(mapKey) ?? [];
      values.push({ ...source, referenced: tokens.has(normalizedKey), valueHash: hash(stableValue(value)) });
      valuesByIdentityAndKey.set(mapKey, values);
    };

    for (const row of emailRows) {
      const email = normalizeEmail(row.email);
      if (!email) continue;
      const identity = `email:${email}`;
      const tokens = templateTokens(...(row.sequence ?? []).flatMap((step) => [step.subject, step.body]));
      const source = { channel: "email" as const, rowId: row.id, campaignId: row.campaignId, active: row.campaignStatus === "active" };
      for (const [key, value] of Object.entries(row.customFields ?? {})) add(identity, key, value, source, tokens);
      add(identity, "firstName", row.firstName, source, tokens);
      add(identity, "lastName", row.lastName, source, tokens);
      add(identity, "company", row.company, source, tokens);
    }

    for (const row of linkedinRows) {
      const linkedin = linkedinFromLeadData(row.leadData);
      const email = emailFromLeadData(row.leadData);
      const identity = legacyPersonIdentityKey({ email, linkedinUrl: linkedin });
      if (!identity) continue;
      const tokens = templateTokens(...row.campaignTemplates, ...row.leadTemplates);
      const source = { channel: "linkedin" as const, rowId: row.id, campaignId: row.campaignId, active: row.campaignStatus === "ACTIVE" };
      for (const [key, value] of Object.entries(stripLegacyIdentityFields(row.leadData ?? {}))) add(identity, key, value, source, tokens);
      add(identity, "name", row.name, source, tokens);
      add(identity, "headline", row.headline, source, tokens);
      add(identity, "location", row.location, source, tokens);
      add(identity, "profilePictureUrl", row.profilePictureUrl, source, tokens);
    }

    const conflicts = [...valuesByIdentityAndKey.entries()].flatMap(([mapKey, values]) => {
      const distinctValues = new Set(values.map((value) => value.valueHash));
      if (distinctValues.size <= 1) return [];
      const separator = mapKey.indexOf("\u0000");
      const identity = mapKey.slice(0, separator);
      const key = mapKey.slice(separator + 1);
      const activeTemplateImpact = values.some((value) => value.active && value.referenced);
      return [{
        identityHash: hash(identity),
        identityType: identity.startsWith("email:") ? "email" : "linkedin",
        key,
        distinctValues: distinctValues.size,
        sourceRows: values.length,
        activeTemplateImpact,
        sources: values.map((value) => ({ ...value })),
      }];
    });
    const summary = {
      auditedAt: new Date().toISOString(),
      readOnly: true,
      conflictGroups: conflicts.length,
      activeTemplateConflictGroups: conflicts.filter((conflict) => conflict.activeTemplateImpact).length,
      inactiveOrUnreferencedConflictGroups: conflicts.filter((conflict) => !conflict.activeTemplateImpact).length,
      affectedIdentities: new Set(conflicts.map((conflict) => conflict.identityHash)).size,
      byChannel: {
        email: conflicts.filter((conflict) => conflict.identityType === "email").length,
        linkedin: conflicts.filter((conflict) => conflict.identityType === "linkedin").length,
      },
    };
    const reportPath = resolve("reports/migration/legacy-raw-conflicts.json");
    await mkdir(resolve("reports/migration"), { recursive: true });
    await writeFile(reportPath, `${JSON.stringify({ summary, conflicts }, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify(summary, null, 2));
    console.log(`Redacted report written to ${reportPath}`);
    if (summary.activeTemplateConflictGroups > 0) {
      console.error("Migration blocked: active templates reference conflicting legacy values.");
      process.exitCode = 2;
    }
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
