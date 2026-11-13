/**
 * Backfills people and the direct person_id on both live outreach engines.
 *
 * Dry-run (default): bun --conditions=react-server scripts/backfill-campaign-people.ts
 * Apply:             bun --conditions=react-server scripts/backfill-campaign-people.ts --apply
 *
 * Do not run this until the schema preparation and live-database preflight
 * have been approved. People are matched by identity and each native campaign
 * row receives that person's direct ID.
 *
 * Runs in ORGANIZATION_ID, or the initial organization when it is unset
 * (bun run --conditions=react-server).
 */
import { runScriptInOrganization } from "./lib/organization";
import { db } from "../src/lib/db";
import { outreachLeads } from "../src/lib/outreach/schema";
import { leads as linkedinLeads } from "../src/lib/linkedin/schema";
import { createProvisionalPerson, enrichPersonById, upsertPerson, withLeadTransaction } from "../src/lib/leads/records";
import { inferLinkedinApi, legacyPersonIdentityKey, linkedinSourceIdentityKey, normalizeEmail, normalizeLinkedinSlug } from "../src/lib/leads/identity";
import { mergeLegacyRawRecords, stripLegacyIdentityFields, type LegacyRawRecord } from "../src/lib/leads/legacyRaw";
import { eq, isNull, sql } from "drizzle-orm";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const APPLY = process.argv.includes("--apply");

function integerArg(name: string): number | null {
  const raw = process.argv.find((value) => value.startsWith(`${name}=`))?.slice(name.length + 1);
  if (raw === undefined) return null;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < 0) throw new Error(`${name} must be a non-negative integer`);
  return value;
}

async function processConcurrently<T>(
  rows: T[],
  label: string,
  processRow: (row: T) => Promise<void>,
) {
  let cursor = 0;
  let completed = 0;
  const requestedConcurrency = Number(process.env.PEOPLE_BACKFILL_CONCURRENCY ?? 8);
  const concurrency = Number.isSafeInteger(requestedConcurrency) && requestedConcurrency > 0
    ? Math.min(requestedConcurrency, 32)
    : 8;
  const workers = Array.from({ length: Math.min(concurrency, rows.length) }, async () => {
    while (true) {
      const index = cursor++;
      if (index >= rows.length) return;
      await processRow(rows[index]);
      completed += 1;
      if (completed % 250 === 0 || completed === rows.length) {
        console.log(`${label}: ${completed}/${rows.length}`);
      }
    }
  });
  await Promise.all(workers);
}

function identityHash(value: string) {
  return createHash("sha256").update(value).digest("hex");
}

async function writeDecisionReport(
  stage: "planned" | "applied",
  rows: Array<Record<string, unknown>>,
) {
  const directory = resolve("reports/migration");
  await mkdir(directory, { recursive: true });
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const path = resolve(directory, `backfill-decisions-${timestamp}-${stage}.json`);
  await writeFile(path, `${JSON.stringify({ createdAt: new Date().toISOString(), stage, rows }, null, 2)}\n`, { flag: "wx", mode: 0o600 });
  console.log(`Backfill ${stage} ledger written to ${path}`);
}

function legacyProfileData(leadData: unknown) {
  return leadData && typeof leadData === "object" ? leadData as Record<string, unknown> : {};
}

function canonicalLinkedinFromLegacy(leadData: unknown): string | null {
  const raw = legacyProfileData(leadData);
  for (const candidate of [raw.public_identifier, raw.public_profile_url]) {
    if (typeof candidate !== "string") continue;
    const normalized = normalizeLinkedinSlug(candidate);
    if (normalized) return normalized;
  }
  return null;
}

function emailFromLegacy(leadData: unknown): string | null {
  const raw = legacyProfileData(leadData);
  if (typeof raw.email === "string") return normalizeEmail(raw.email);
  const contactInfo = raw.contact_info && typeof raw.contact_info === "object"
    ? raw.contact_info as Record<string, unknown>
    : null;
  const emails = Array.isArray(contactInfo?.emails) ? contactInfo.emails : [];
  for (const item of emails) {
    const value = typeof item === "string"
      ? item
      : item && typeof item === "object" && typeof (item as Record<string, unknown>).email === "string"
        ? (item as Record<string, unknown>).email as string
        : item && typeof item === "object" && typeof (item as Record<string, unknown>).value === "string"
          ? (item as Record<string, unknown>).value as string
        : null;
    const normalized = normalizeEmail(value);
    if (normalized) return normalized;
  }
  return null;
}

function providerConfirmedLinkedinAliases(rows: Array<{
  id: string;
  leadData: unknown;
  providerId: string | null;
  requestSentAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
}>) {
  const candidatesByEmail = new Map<string, Array<{ slug: string; providerId: string | null; observedAt: Date; id: string }>>();
  for (const row of rows) {
    const email = emailFromLegacy(row.leadData);
    const slug = canonicalLinkedinFromLegacy(row.leadData);
    if (!email || !slug) continue;
    const candidates = candidatesByEmail.get(email) ?? [];
    // updatedAt is execution state, not source chronology. Collision cleanup
    // deliberately updates a superseded Lead, so using it here can make an old
    // slug look newer solely because cleanup ran before backfill.
    candidates.push({ slug, providerId: row.providerId, observedAt: row.requestSentAt ?? row.createdAt, id: row.id });
    candidatesByEmail.set(email, candidates);
  }

  const result = new Map<string, string>();
  for (const [email, candidates] of candidatesByEmail) {
    const slugs = new Set(candidates.map((candidate) => candidate.slug));
    if (slugs.size === 1) {
      result.set(email, candidates[0].slug);
      continue;
    }
    const providerIds = new Set(candidates.map((candidate) => candidate.providerId).filter(Boolean));
    if (providerIds.size !== 1 || candidates.some((candidate) => !candidate.providerId)) {
      throw new Error(`Backfill blocked: ${email} maps to multiple LinkedIn identities without one shared provider ID`);
    }
    const newest = [...candidates].sort((left, right) =>
      right.observedAt.getTime() - left.observedAt.getTime() || right.id.localeCompare(left.id)
    )[0];
    result.set(email, newest.slug);
  }
  return result;
}

function mergedRawByIdentity(rows: { identity: string; record: LegacyRawRecord }[]) {
  const byIdentity = new Map<string, LegacyRawRecord[]>();
  for (const row of rows) {
    const records = byIdentity.get(row.identity) ?? [];
    records.push(row.record);
    byIdentity.set(row.identity, records);
  }
  return new Map([...byIdentity.entries()].map(([identity, records]) => [identity, mergeLegacyRawRecords(records)]));
}

function duplicatePlannedMemberships(keys: Array<{ channel: "email" | "linkedin"; campaignId: string | null; personKey: string }>) {
  const counts = new Map<string, number>();
  for (const item of keys) {
    if (!item.campaignId) continue;
    const key = `${item.channel}\u0000${item.campaignId}\u0000${item.personKey}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()].filter(([, count]) => count > 1).map(([key, count]) => ({ key, count }));
}

async function assertSchemaPrepared() {
  const rows = await db.execute<{ table_name: string; column_name: string }>(sql`
    select table_name, column_name
    from information_schema.columns
    where table_schema = 'public'
      and (
        (table_name = 'outreach_leads' and column_name = 'person_id')
        or (table_name = 'Lead' and column_name in ('personId', 'sourceLinkedinIdentifier', 'sourceLinkedinApi'))
      )
  `);
  const present = new Set(rows.map((row) => `${row.table_name}.${row.column_name}`));
  const missing = [
    "outreach_leads.person_id",
    "Lead.personId",
    "Lead.sourceLinkedinIdentifier",
    "Lead.sourceLinkedinApi",
  ].filter((column) => !present.has(column));
  if (missing.length) {
    throw new Error(
      `Schema preparation has not been run; missing ${missing.join(", ")}. Run scripts/create-lead-tables.ts before this backfill.`,
    );
  }
}

async function main() {
  await assertSchemaPrepared();
  const [allEmailRows, allLinkedinRows] = await Promise.all([
    db.select().from(outreachLeads),
    db.select().from(linkedinLeads),
  ]);
  const emailRows = allEmailRows.filter((lead) => !lead.personId);
  const linkedinRows = allLinkedinRows.filter((lead) => !lead.personId);
  console.log(`Found ${emailRows.length} Email campaign rows and ${linkedinRows.length} LinkedIn campaign rows.`);
  if (APPLY) {
    const expectedEmail = integerArg("--expected-email");
    const expectedLinkedin = integerArg("--expected-linkedin");
    if (expectedEmail === null || expectedLinkedin === null) {
      throw new Error("Apply requires --expected-email=N and --expected-linkedin=N from the immediately preceding dry run");
    }
    if (expectedEmail !== emailRows.length || expectedLinkedin !== linkedinRows.length) {
      throw new Error(
        `Backfill row counts changed: expected Email ${expectedEmail}/LinkedIn ${expectedLinkedin}, found Email ${emailRows.length}/LinkedIn ${linkedinRows.length}`,
      );
    }
  }
  const emailRowsWithoutIdentity = emailRows.filter((lead) => !normalizeEmail(lead.email)).length;
  const linkedinRowsWithoutIdentity = linkedinRows.filter((lead) => !lead.linkedinUrl?.trim()).length;
  if (emailRowsWithoutIdentity || linkedinRowsWithoutIdentity) {
    throw new Error(
      `Backfill blocked by missing legacy identities: ${emailRowsWithoutIdentity} Email row(s), ${linkedinRowsWithoutIdentity} LinkedIn row(s).`,
    );
  }
  // Identity and raw-value decisions must use the complete legacy dataset.
  // Restricting this evidence to NULL person IDs makes a restarted backfill
  // choose different winners after earlier batches have committed.
  const linkedinAliasByEmail = providerConfirmedLinkedinAliases(allLinkedinRows);
  const plannedMembershipDuplicates = duplicatePlannedMemberships([
    ...emailRows.flatMap((lead) => {
      const email = normalizeEmail(lead.email);
      return email ? [{ channel: "email" as const, campaignId: lead.campaignId, personKey: `email:${email}` }] : [];
    }),
    ...linkedinRows.flatMap((lead) => {
      const email = emailFromLegacy(lead.leadData);
      const canonical = canonicalLinkedinFromLegacy(lead.leadData);
      const resolvedLinkedin = email ? linkedinAliasByEmail.get(email) ?? canonical : canonical;
      const personKey = email
        ? `email:${email}`
        : resolvedLinkedin
          ? `linkedin:${resolvedLinkedin}`
          : lead.providerId
            ? `provider:${lead.providerId}`
            : `source:${lead.linkedinUrl!.trim().toLowerCase()}`;
      return [{ channel: "linkedin" as const, campaignId: lead.campaignId, personKey }];
    }),
  ]);
  if (plannedMembershipDuplicates.length) {
    throw new Error(
      `Backfill blocked by ${plannedMembershipDuplicates.length} duplicate campaign membership group(s) after identity reconciliation.`,
    );
  }
  const legacyRaw = mergedRawByIdentity([
    ...allEmailRows.filter((lead) => lead.email).map((lead) => ({
      identity: `email:${lead.email!.trim().toLowerCase()}`,
      record: {
        raw: { ...(lead.customFields ?? {}), firstName: lead.firstName, lastName: lead.lastName, company: lead.company },
        sourceRowId: `outreach_leads:${lead.id}`,
        // Campaign execution updates must not change which imported value wins.
        observedAt: lead.createdAt,
      },
    })),
    ...allLinkedinRows.flatMap((lead) => {
      const linkedinUrl = canonicalLinkedinFromLegacy(lead.leadData);
      const email = emailFromLegacy(lead.leadData);
      const identity = legacyPersonIdentityKey({ email, linkedinUrl });
      return identity ? [{
        identity,
        record: {
          raw: {
            ...stripLegacyIdentityFields((lead.leadData as Record<string, unknown> | null) ?? {}),
            name: lead.name,
            headline: lead.headline,
            location: lead.location,
            profilePictureUrl: lead.profilePictureUrl,
          },
          sourceRowId: `Lead:${lead.id}`,
          // requestSentAt/createdAt are immutable source chronology; updatedAt
          // changes during collision cleanup and would make ordering dependent
          // on which migration step ran first.
          observedAt: lead.requestSentAt ?? lead.createdAt,
        },
      }] : [];
    }),
  ]);

  const [duplicateEmailMemberships, duplicateLinkedinMemberships] = await Promise.all([
    db.execute(sql`
      select ol.campaign_id, lower(coalesce(p.email, ol.email)) as identity, count(*)::int as count
      from outreach_leads ol
      left join people p on p.id = ol.person_id
      where coalesce(p.email, ol.email) is not null
      group by ol.campaign_id, lower(coalesce(p.email, ol.email))
      having count(*) > 1
      limit 20
    `),
    db.execute(sql`
      select l."campaignId", lower(coalesce(p.linkedin_url, l."linkedinUrl")) as identity, count(*)::int as count
      from "Lead" l
      left join people p on p.id = l."personId"
      where coalesce(p.linkedin_url, l."linkedinUrl") is not null and l."campaignId" is not null
      group by l."campaignId", lower(coalesce(p.linkedin_url, l."linkedinUrl"))
      having count(*) > 1
      limit 20
    `),
  ]);
  if (duplicateEmailMemberships.length || duplicateLinkedinMemberships.length) {
    throw new Error(
      `Backfill blocked by duplicate campaign memberships: ${duplicateEmailMemberships.length} Email group(s), ${duplicateLinkedinMemberships.length} LinkedIn group(s). Deduplicate them before applying.`,
    );
  }
  const plannedDecisions = [
    ...emailRows.map((lead) => {
      const identity = legacyPersonIdentityKey({ email: lead.email });
      return { channel: "email", rowId: lead.id, campaignId: lead.campaignId, identityHash: identity ? identityHash(identity) : null, matchRule: "email" };
    }),
    ...linkedinRows.map((lead) => {
      const email = emailFromLegacy(lead.leadData);
      const canonical = canonicalLinkedinFromLegacy(lead.leadData);
      const resolvedLinkedin = email ? linkedinAliasByEmail.get(email) ?? canonical : canonical;
      const sourceIdentifier = lead.providerId && resolvedLinkedin ? null : lead.providerId ?? lead.linkedinUrl;
      const sourceApi = lead.providerId ? null : inferLinkedinApi(lead.linkedinUrl);
      const identity = legacyPersonIdentityKey({ email, linkedinUrl: resolvedLinkedin })
        ?? linkedinSourceIdentityKey(sourceIdentifier, sourceApi);
      return {
        channel: "linkedin",
        rowId: lead.id,
        campaignId: lead.campaignId,
        identityHash: identity ? identityHash(identity) : null,
        matchRule: email ? "email" : resolvedLinkedin ? "linkedin" : lead.providerId ? "provider" : "source",
      };
    }),
  ];
  await writeDecisionReport("planned", plannedDecisions);
  if (!APPLY) {
    console.log("Dry run only. Re-run with --apply after reviewing these counts.");
    return;
  }

  const appliedDecisions: Array<Record<string, unknown>> = [];
  await processConcurrently(emailRows, "Email", async (lead) => {
    await withLeadTransaction(async (tx) => {
      if (!lead.email) throw new Error(`Email lead ${lead.id} has no legacy email identity`);
      const person = await upsertPerson(tx, {
        email: lead.email,
        raw: legacyRaw.get(`email:${lead.email.trim().toLowerCase()}`) ?? {},
        source: `backfill:outreach_leads:${lead.id}`,
      });
      await tx.update(outreachLeads).set({ personId: person.id }).where(eq(outreachLeads.id, lead.id));
      appliedDecisions.push({ channel: "email", rowId: lead.id, campaignId: lead.campaignId, personId: person.id });
    });
  });

  await processConcurrently(linkedinRows, "LinkedIn", async (lead) => {
    await withLeadTransaction(async (tx) => {
      if (!lead.linkedinUrl) throw new Error(`LinkedIn lead ${lead.id} has no legacy LinkedIn identity`);
      const canonicalLinkedin = canonicalLinkedinFromLegacy(lead.leadData);
      const email = emailFromLegacy(lead.leadData);
      const resolvedLinkedin = email ? linkedinAliasByEmail.get(email) ?? canonicalLinkedin : canonicalLinkedin;
      const personInput = {
        linkedinUrl: resolvedLinkedin,
        email,
        raw: legacyRaw.get(email ? `email:${email}` : resolvedLinkedin ? `linkedin:${resolvedLinkedin}` : "") ?? {
          ...stripLegacyIdentityFields((lead.leadData as Record<string, unknown> | null) ?? {}),
          ...(lead.name ? { name: lead.name } : {}),
          ...(lead.headline ? { headline: lead.headline } : {}),
          ...(lead.location ? { location: lead.location } : {}),
          ...(lead.profilePictureUrl ? { profilePictureUrl: lead.profilePictureUrl } : {}),
        },
        source: `backfill:Lead:${lead.id}`,
      };
      const sourceIdentifier = lead.providerId && resolvedLinkedin ? null : lead.providerId ?? lead.linkedinUrl;
      const sourceApi = lead.providerId ? null : inferLinkedinApi(lead.linkedinUrl);
      let person;
      if (resolvedLinkedin || email) {
        person = await upsertPerson(tx, personInput);
      } else {
        const sourceKey = linkedinSourceIdentityKey(sourceIdentifier, sourceApi);
        if (!sourceKey) throw new Error(`LinkedIn lead ${lead.id} has no provisional source identity`);
        await tx.execute(sql`select pg_advisory_xact_lock(hashtextextended(${sourceKey}, 0))`);
        const linked = await tx.execute<{ personId: string }>(sql`
          select distinct "personId" as "personId"
          from "Lead"
          where "personId" is not null
            and lower("sourceLinkedinIdentifier") = lower(${sourceIdentifier})
            and "sourceLinkedinApi" is not distinct from ${sourceApi}
          limit 2
        `);
        if (linked.length > 1) {
          throw new Error(`Backfill blocked: unresolved source ${sourceKey} already maps to multiple People`);
        }
        person = linked[0]
          ? await enrichPersonById(tx, linked[0].personId, personInput)
          : await createProvisionalPerson(tx, personInput);
      }
      await tx.update(linkedinLeads).set({
        personId: person.id,
        sourceLinkedinIdentifier: sourceIdentifier,
        sourceLinkedinApi: sourceApi,
      }).where(eq(linkedinLeads.id, lead.id));
      appliedDecisions.push({ channel: "linkedin", rowId: lead.id, campaignId: lead.campaignId, personId: person.id });
    });
  });

  const [[emailMissing], [linkedinMissing], [emailIdentityMissing], [linkedinIdentityMissing]] = await Promise.all([
    db.select({ count: sql<number>`count(*)::int` }).from(outreachLeads).where(isNull(outreachLeads.personId)),
    db.select({ count: sql<number>`count(*)::int` }).from(linkedinLeads).where(isNull(linkedinLeads.personId)),
    db.execute<{ count: number }>(sql`select count(*)::int as count from outreach_leads ol left join people p on p.id = ol.person_id where ol.person_id is null or p.email is null`),
    db.execute<{ count: number }>(sql`
      select count(*)::int as count
      from "Lead" l
      left join people p on p.id = l."personId"
      where
        (l.status in ('REQUEST_SENT', 'CONNECTED', 'ACCEPT_MESSAGE_SENT', 'FOLLOW_UP_1_SENT', 'FOLLOW_UP_2_SENT', 'FOLLOW_UP_3_SENT')
          and (l."personId" is null or l."providerId" is null))
        or (l.status = 'PENDING' and (
          l."personId" is null
          or ((p.linkedin_url is null or l."providerId" is null) and l."sourceLinkedinIdentifier" is null)
        ))
    `),
  ]);
  if (emailMissing.count || emailIdentityMissing.count || linkedinIdentityMissing.count) {
    throw new Error(`Cannot finalize: missing person links — Email ${emailMissing.count}, LinkedIn ${linkedinMissing.count}; linked People missing channel identity — Email ${emailIdentityMissing.count}, LinkedIn ${linkedinIdentityMissing.count}`);
  }
  await writeDecisionReport("applied", appliedDecisions);
  console.log(
    "Backfill complete. Run scripts/finalize-lead-tables.ts in check-only mode; final constraints are a separate approved step.",
  );
}

runScriptInOrganization(main).catch((error) => {
  console.error(error);
  process.exit(1);
});
