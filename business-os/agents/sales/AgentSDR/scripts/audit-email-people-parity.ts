/**
 * Proves that switching active Email campaigns from legacy outreach_leads
 * profile columns to People does not change recipients or pending template
 * substitutions. This is read-only and is intended to run after backfill but
 * before workers are resumed.
 */
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "pg";
import { personVariables, type CompanyVariableSource, type PersonVariableSource } from "../src/lib/leads/variables";

type SequenceStep = { stepNumber?: number; subject?: string; body?: string; waitDays?: number };

type ParityRow = {
  id: string;
  campaignId: string;
  legacyEmail: string | null;
  legacyFirstName: string | null;
  legacyLastName: string | null;
  legacyCompany: string | null;
  legacyCustomFields: Record<string, unknown> | null;
  sequenceStatus: string;
  currentStep: number;
  sequence: SequenceStep[];
  personId: string | null;
  personEmail: string | null;
  personLinkedinUrl: string | null;
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

function text(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

/** Mirrors the pre-People fillTemplate precedence without resolving spin text. */
export function legacyEmailVariables(row: Pick<ParityRow,
  "legacyFirstName" | "legacyLastName" | "legacyCompany" | "legacyCustomFields"
>): Record<string, string> {
  const variables: Record<string, string> = {};
  for (const [key, value] of Object.entries(row.legacyCustomFields ?? {})) {
    const rendered = text(value);
    if (rendered !== null) variables[key] = rendered;
  }
  if (row.legacyFirstName !== null) variables.firstName = row.legacyFirstName;
  if (row.legacyLastName !== null) variables.lastName = row.legacyLastName;
  if (row.legacyCompany !== null) variables.company = row.legacyCompany;
  return variables;
}

/** Template substitution only; spin alternatives remain untouched on both sides. */
export function substituteVariables(template: string, variables: Record<string, string>): string {
  const lookup = new Map(Object.entries(variables).map(([key, value]) => [key.toLowerCase(), value]));
  return template.replace(
    /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g,
    (match, key: string) => key.toLowerCase() === "signature" ? match : lookup.get(key.toLowerCase()) ?? "",
  );
}

function pendingSteps(row: ParityRow): SequenceStep[] {
  if (["sequence_completed", "reply_received", "bounced", "suppressed"].includes(row.sequenceStatus)) return [];
  return (row.sequence ?? []).slice(Math.max(0, row.currentStep));
}

export function compareEmailParityRow(row: ParityRow) {
  const reasons: string[] = [];
  if (!row.personId) reasons.push("missing_person");
  if (!row.personEmail) reasons.push("missing_person_email");
  // A NULL legacy email identifies a People-native enrollment created after
  // cutover. There is no legacy snapshot to compare in that case; treating
  // NULL as a changed recipient makes every new campaign fail this migration
  // audit even though runtime correctly resolves the address from people.
  const hasLegacySnapshot = row.legacyEmail !== null;
  if (hasLegacySnapshot && row.legacyEmail !== row.personEmail) reasons.push("recipient_changed");

  const person: PersonVariableSource = {
    email: row.personEmail,
    linkedinUrl: row.personLinkedinUrl,
    firstName: row.personFirstName,
    lastName: row.personLastName,
    fullName: row.personFullName,
    title: row.personTitle,
    raw: row.personRaw,
  };
  const company: CompanyVariableSource | null = row.companyDomain ? {
    domain: row.companyDomain,
    name: row.companyName,
    linkedinUrl: row.companyLinkedinUrl,
    raw: row.companyRaw,
  } : null;
  const changedSteps: number[] = [];
  if (hasLegacySnapshot) {
    const legacyVariables = legacyEmailVariables(row);
    const unifiedVariables = personVariables(person, company);
    for (const [offset, step] of pendingSteps(row).entries()) {
      const oldSubject = substituteVariables(step.subject ?? "", legacyVariables);
      const newSubject = substituteVariables(step.subject ?? "", unifiedVariables);
      const oldBody = substituteVariables(step.body ?? "", legacyVariables);
      const newBody = substituteVariables(step.body ?? "", unifiedVariables);
      if (oldSubject !== newSubject || oldBody !== newBody) changedSteps.push(row.currentStep + offset);
    }
  }
  if (changedSteps.length) reasons.push("pending_render_changed");
  return { reasons, changedSteps };
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set");
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: false },
    application_name: "agentsdr-readonly-email-people-parity",
  });
  await client.connect();
  try {
    await client.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL statement_timeout = '60s'");
    const { rows } = await client.query<ParityRow>(`
      SELECT l.id, l.campaign_id AS "campaignId", l.email AS "legacyEmail",
        l.first_name AS "legacyFirstName", l.last_name AS "legacyLastName",
        l.company AS "legacyCompany", l.custom_fields AS "legacyCustomFields",
        l.sequence_status AS "sequenceStatus", l.current_step AS "currentStep",
        c.sequence, l.person_id AS "personId", p.email AS "personEmail",
        p.linkedin_url AS "personLinkedinUrl", p.first_name AS "personFirstName",
        p.last_name AS "personLastName", p.full_name AS "personFullName",
        p.title AS "personTitle", p.raw AS "personRaw",
        co.domain AS "companyDomain", co.name AS "companyName",
        co.linkedin_url AS "companyLinkedinUrl", co.raw AS "companyRaw"
      FROM outreach_leads l
      JOIN outreach_campaigns c ON c.id = l.campaign_id
      LEFT JOIN people p ON p.id = l.person_id
      LEFT JOIN companies co ON co.id = p.company_id
      WHERE c.status = 'active'
      ORDER BY l.id
    `);
    await client.query("ROLLBACK");

    const mismatches = rows.flatMap((row) => {
      const comparison = compareEmailParityRow(row);
      return comparison.reasons.length ? [{
        leadId: row.id,
        campaignId: row.campaignId,
        reasons: comparison.reasons,
        changedSteps: comparison.changedSteps,
      }] : [];
    });
    const report = {
      checkedAt: new Date().toISOString(),
      readOnly: true,
      passed: mismatches.length === 0,
      activeLeadsChecked: rows.length,
      mismatches,
    };
    await mkdir(resolve("reports/migration"), { recursive: true });
    await writeFile(resolve("reports/migration/email-people-parity-latest.json"), `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify(report, null, 2));
    if (!report.passed) process.exitCode = 2;
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
