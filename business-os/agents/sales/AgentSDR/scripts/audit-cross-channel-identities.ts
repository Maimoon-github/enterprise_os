/** Read-only identity graph audit for the legacy Email and LinkedIn engines. */
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { Client } from "pg";
import { linkedinSourceIdentityKey, normalizeEmail, normalizeLinkedinSlug } from "../src/lib/leads/identity";

function hash(value: string) {
  return createHash("sha256").update(value).digest("hex");
}

function identitiesFromLeadData(value: unknown) {
  const raw = value && typeof value === "object" ? value as Record<string, unknown> : {};
  let linkedin: string | null = null;
  for (const candidate of [raw.public_identifier, raw.public_profile_url]) {
    if (typeof candidate === "string") linkedin ||= normalizeLinkedinSlug(candidate);
  }
  let email = typeof raw.email === "string" ? normalizeEmail(raw.email) : null;
  const contact = raw.contact_info && typeof raw.contact_info === "object"
    ? raw.contact_info as Record<string, unknown>
    : null;
  for (const item of Array.isArray(contact?.emails) ? contact.emails : []) {
    const candidate = typeof item === "string" ? item : item && typeof item === "object"
      ? ((item as Record<string, unknown>).email ?? (item as Record<string, unknown>).value) : null;
    if (!email && typeof candidate === "string") email = normalizeEmail(candidate);
  }
  return { email, linkedin };
}

async function main() {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is not set — check .env.local");
  const client = new Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
    application_name: "agentsdr-readonly-cross-channel-identity-audit",
  });
  await client.connect();
  try {
    await client.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
    await client.query("SET LOCAL statement_timeout = '60s'");
    const { rows: people } = await client.query<{ id: string; email: string | null; linkedinUrl: string | null }>(
      `SELECT id, email, linkedin_url AS "linkedinUrl" FROM people`,
    );
    const { rows: emailLeads } = await client.query<{ id: string; email: string | null; personId: string | null; campaignId: string; active: boolean }>(`
        SELECT l.id, l.email, l.person_id AS "personId", l.campaign_id AS "campaignId", (c.status = 'active') AS active
        FROM outreach_leads l JOIN outreach_campaigns c ON c.id = l.campaign_id
      `);
    const { rows: linkedinLeads } = await client.query<{ id: string; leadData: unknown; legacyLinkedinUrl: string | null; sourceLinkedinIdentifier: string | null; sourceLinkedinApi: string | null; personId: string | null; campaignId: string | null; active: boolean; providerId: string | null; updatedAt: Date }>(`
        SELECT l.id, l."leadData", l."campaignId", (c.status = 'ACTIVE') AS active,
          l."providerId", l."updatedAt", l."linkedinUrl" AS "legacyLinkedinUrl",
          l."sourceLinkedinIdentifier", l."sourceLinkedinApi", l."personId"
        FROM "Lead" l LEFT JOIN "Campaign" c ON c.id = l."campaignId"
      `);
    await client.query("ROLLBACK");

    const peopleByEmail = new Map(people.flatMap((person) => {
      const email = normalizeEmail(person.email);
      return email ? [[email, person.id] as const] : [];
    }));
    const peopleByLinkedin = new Map(people.flatMap((person) => {
      const linkedin = normalizeLinkedinSlug(person.linkedinUrl);
      return linkedin ? [[linkedin, person.id] as const] : [];
    }));
    const duplicatePersonEmails = new Map<string, string[]>();
    const duplicatePersonLinkedins = new Map<string, string[]>();
    for (const person of people) {
      const email = normalizeEmail(person.email);
      const linkedin = normalizeLinkedinSlug(person.linkedinUrl);
      if (email) duplicatePersonEmails.set(email, [...(duplicatePersonEmails.get(email) ?? []), person.id]);
      if (linkedin) duplicatePersonLinkedins.set(linkedin, [...(duplicatePersonLinkedins.get(linkedin) ?? []), person.id]);
    }
    const duplicatePeopleIdentities = [
      ...[...duplicatePersonEmails.entries()].filter(([, ids]) => ids.length > 1).map(([identity, personIds]) => ({ kind: "duplicate_people_email", identityHash: hash(identity), personIds })),
      ...[...duplicatePersonLinkedins.entries()].filter(([, ids]) => ids.length > 1).map(([identity, personIds]) => ({ kind: "duplicate_people_linkedin", identityHash: hash(identity), personIds })),
    ];
    const enrollmentPersonContradictions: Array<Record<string, unknown>> = [];
    for (const row of emailLeads) {
      const email = normalizeEmail(row.email);
      const expectedPersonId = email ? peopleByEmail.get(email) : null;
      if (row.personId && expectedPersonId && row.personId !== expectedPersonId) {
        enrollmentPersonContradictions.push({ channel: "email", rowId: row.id, campaignId: row.campaignId, active: row.active, identityHash: hash(email!), linkedPersonId: row.personId, expectedPersonId });
      }
    }
    const emailCampaignsByIdentity = new Map<string, { rowId: string; campaignId: string; active: boolean }[]>();
    for (const row of emailLeads) {
      const email = normalizeEmail(row.email);
      if (!email) continue;
      const matches = emailCampaignsByIdentity.get(email) ?? [];
      matches.push({ rowId: row.id, campaignId: row.campaignId, active: row.active });
      emailCampaignsByIdentity.set(email, matches);
    }

    const crossChannel = [];
    const existingPersonContradictions = [];
    const emailsToLinkedin = new Map<string, Set<string>>();
    const linkedinToEmails = new Map<string, Set<string>>();
    const evidenceByEmail = new Map<string, { linkedinHash: string; providerId: string | null; rowId: string; campaignId: string | null; active: boolean; updatedAt: Date }[]>();
    const evidenceByLinkedin = new Map<string, { emailHash: string; rowId: string; campaignId: string | null; active: boolean }[]>();
    const sourcePeople = new Map<string, Set<string>>();
    for (const row of linkedinLeads) {
      const { email, linkedin } = identitiesFromLeadData(row.leadData);
      if (email && linkedin) {
        const linkedins = emailsToLinkedin.get(email) ?? new Set<string>();
        linkedins.add(linkedin);
        emailsToLinkedin.set(email, linkedins);
        const emails = linkedinToEmails.get(linkedin) ?? new Set<string>();
        emails.add(email);
        linkedinToEmails.set(linkedin, emails);
        const emailEvidence = evidenceByEmail.get(email) ?? [];
        emailEvidence.push({ linkedinHash: hash(linkedin), providerId: row.providerId, rowId: row.id, campaignId: row.campaignId, active: row.active, updatedAt: row.updatedAt });
        evidenceByEmail.set(email, emailEvidence);
        const linkedinEvidence = evidenceByLinkedin.get(linkedin) ?? [];
        linkedinEvidence.push({ emailHash: hash(email), rowId: row.id, campaignId: row.campaignId, active: row.active });
        evidenceByLinkedin.set(linkedin, linkedinEvidence);
      }
      const personByEmail = email ? peopleByEmail.get(email) : null;
      const personByLinkedin = linkedin ? peopleByLinkedin.get(linkedin) : null;
      if (personByEmail && personByLinkedin && personByEmail !== personByLinkedin) {
        existingPersonContradictions.push({
          linkedinLeadId: row.id,
          emailHash: hash(email!),
          linkedinHash: hash(linkedin!),
          personByEmail,
          personByLinkedin,
        });
      }
      const expectedPersonId = personByEmail ?? personByLinkedin ?? null;
      if (row.personId && expectedPersonId && row.personId !== expectedPersonId) {
        enrollmentPersonContradictions.push({
          channel: "linkedin", rowId: row.id, campaignId: row.campaignId, active: row.active,
          emailHash: email ? hash(email) : null, linkedinHash: linkedin ? hash(linkedin) : null,
          linkedPersonId: row.personId, expectedPersonId,
        });
      }
      const sourceKey = linkedinSourceIdentityKey(row.sourceLinkedinIdentifier, row.sourceLinkedinApi);
      if (sourceKey && row.personId) {
        const ids = sourcePeople.get(sourceKey) ?? new Set<string>();
        ids.add(row.personId);
        sourcePeople.set(sourceKey, ids);
      }
      const emailCampaignRows = email ? emailCampaignsByIdentity.get(email) ?? [] : [];
      if (emailCampaignRows.length) {
        crossChannel.push({
          linkedinLeadId: row.id,
          linkedinCampaignId: row.campaignId,
          linkedinCampaignActive: row.active,
          emailHash: hash(email!),
          linkedinHash: linkedin ? hash(linkedin) : null,
          emailCampaignRows,
          activeInBoth: row.active && emailCampaignRows.some((candidate) => candidate.active),
        });
      }
    }

    const emailLinkedinConflicts = [...emailsToLinkedin.entries()].filter(([, values]) => values.size > 1).map(([email, values]) => {
      const evidence = evidenceByEmail.get(email) ?? [];
      const providerIds = new Set(evidence.map((row) => row.providerId).filter(Boolean));
      const providerConfirmedAlias = providerIds.size === 1 && evidence.every((row) => row.providerId);
      return {
        kind: "one_email_multiple_linkedin",
        identityHash: hash(email),
        conflictingIdentityHashes: [...values].map(hash),
        active: evidence.some((row) => row.active),
        resolution: providerConfirmedAlias ? "provider_confirmed_alias_use_newest" : "manual_review",
        evidence,
      };
    });
    const legacyContradictions = [
      ...emailLinkedinConflicts.filter((conflict) => conflict.resolution === "manual_review"),
      ...[...linkedinToEmails.entries()].filter(([, values]) => values.size > 1).map(([linkedin, values]) => ({
        kind: "one_linkedin_multiple_emails",
        identityHash: hash(linkedin),
        conflictingIdentityHashes: [...values].map(hash),
        active: (evidenceByLinkedin.get(linkedin) ?? []).some((row) => row.active),
        evidence: evidenceByLinkedin.get(linkedin) ?? [],
      })),
    ];
    const unresolvedSourceContradictions = [...sourcePeople.entries()]
      .filter(([, personIds]) => personIds.size > 1)
      .map(([source, personIds]) => ({ sourceHash: hash(source), personIds: [...personIds] }));
    const summary = {
      auditedAt: new Date().toISOString(),
      readOnly: true,
      crossChannelLinkedinRows: crossChannel.length,
      activeInBothRows: crossChannel.filter((row) => row.activeInBoth).length,
      existingPersonContradictions: existingPersonContradictions.length,
      enrollmentPersonContradictions: enrollmentPersonContradictions.length,
      duplicatePeopleIdentities: duplicatePeopleIdentities.length,
      unresolvedSourceContradictions: unresolvedSourceContradictions.length,
      legacyIdentityContradictions: legacyContradictions.length,
      providerConfirmedAliases: emailLinkedinConflicts.filter((conflict) => conflict.resolution === "provider_confirmed_alias_use_newest").length,
    };
    const reportPath = resolve("reports/migration/cross-channel-identities.json");
    await mkdir(resolve("reports/migration"), { recursive: true });
    await writeFile(reportPath, `${JSON.stringify({ summary, crossChannel, existingPersonContradictions, enrollmentPersonContradictions, duplicatePeopleIdentities, unresolvedSourceContradictions, providerConfirmedAliases: emailLinkedinConflicts.filter((conflict) => conflict.resolution !== "manual_review"), legacyContradictions }, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify(summary, null, 2));
    console.log(`Redacted report written to ${reportPath}`);
    if (existingPersonContradictions.length || enrollmentPersonContradictions.length || duplicatePeopleIdentities.length || unresolvedSourceContradictions.length || legacyContradictions.length) process.exitCode = 2;
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
