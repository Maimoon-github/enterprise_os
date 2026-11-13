import { and, eq, inArray, or, sql } from "drizzle-orm";
import { randomUUID } from "node:crypto";
import { db } from "@/lib/db";
import { campaigns, leads } from "@/lib/linkedin/schema";
import { companies, importRuns, people } from "@/lib/leads/schema";
import { enrichPersonById, resolvePersonNames, upsertPerson, withLeadTransaction, type LeadMutationContext } from "@/lib/leads/records";
import { inferLinkedinApi, linkedinSourceIdentityKey, normalizeCompanyDomain, normalizeEmail, normalizeLinkedinApiHint, normalizeLinkedinSourceIdentifier, type LinkedinApiHint } from "@/lib/leads/identity";
import type { FailedLeadExportRow } from "@/lib/linkedin/exportFailedLeads";
import { mappedLeadRowToRaw } from "@/lib/linkedin/exportFailedLeads";
import { invitationMessageLength, isInvitationMessageTooLong } from "@/lib/linkedin/invitationMessage";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";

/** Keep bulk statements comfortably below PostgreSQL's bind-parameter limit. */
export const IMPORT_BATCH_SIZE = 200;

/**
 * Serializes a batch of identity keys through one advisory-lock statement.
 *
 * Every key must arrive as a bound parameter. Writing a namespace into the
 * template instead — sql`company:${domain}` — puts the literal text in the
 * statement and leaves `company:$1`, which Postgres rejects with a syntax
 * error at ":". Prefix the value, not the SQL.
 */
export function advisoryLockStatement(keys: string[]) {
  return sql`
        SELECT pg_advisory_xact_lock(hashtextextended(lock_key, 0))
        FROM (
          SELECT lock_key
          FROM unnest(ARRAY[${sql.join(keys.map((value) => sql`${value}`), sql`, `)}]::text[]) AS keys(lock_key)
          ORDER BY lock_key
        ) AS lock_keys
      `;
}

export function chunkArray<T>(values: T[], size: number): T[][] {
  if (!Number.isInteger(size) || size <= 0) throw new Error("Batch size must be a positive integer");
  const chunks: T[][] = [];
  for (let index = 0; index < values.length; index += size) chunks.push(values.slice(index, index + size));
  return chunks;
}

export const IMPORT_FAILURE = {
  CAMPAIGN_REQUIRED: "A destination campaign is required; importing or exporting a list does not create People",
  MISSING_URL: "Missing LinkedIn URL",
  INVALID_URL: "Invalid LinkedIn URL",
  INVALID_EMAIL: "Invalid email address",
  DUPLICATE_IN_FILE: "Duplicate in file",
  EMAIL_IDENTITY_CONFLICT: "Email belongs to multiple LinkedIn profiles in file",
  INVITATION_TOO_LONG: (length: number) =>
    `Invitation message exceeds 300 characters (${length} characters)`,
  ALREADY_EXISTS: "Lead already exists in this campaign",
} as const;

export function normalizeSpreadsheetHeader(h: string): string {
  return h.toLowerCase().replace(/[\s_\-]+/g, "").replace(/[^a-z0-9]/g, "");
}

export const SPREADSHEET_COLUMN_MAP: Record<string, string> = {
  linkedinurl: "linkedinUrl",
  linkedinprofile: "linkedinUrl",
  profileurl: "linkedinUrl",
  url: "linkedinUrl",
  linkedinapi: "linkedinApi",
  email: "email",
  workemail: "email",
  firstname: "firstName",
  givenname: "firstName",
  lastname: "lastName",
  familyname: "lastName",
  name: "name",
  fullname: "name",
  headline: "headline",
  tagline: "headline",
  jobtitle: "headline",
  role: "headline",
  company: "companyName",
  companyname: "companyName",
  organisation: "companyName",
  organization: "companyName",
  domain: "companyDomain",
  companydomain: "companyDomain",
  website: "companyDomain",
  companylinkedin: "companyLinkedinUrl",
  companylinkedinurl: "companyLinkedinUrl",
  companylinkedinprofile: "companyLinkedinUrl",
  companypage: "companyLinkedinUrl",
  location: "location",
  city: "location",
  profilepictureurl: "profilePictureUrl",
  profilepicture: "profilePictureUrl",
  pictureurl: "profilePictureUrl",
  photo: "profilePictureUrl",
  campaignname: "campaignName",
  campaign: "campaignName",
  invitationmessage: "invitationMessage",
  invitationmessagemax300chars: "invitationMessage",
  invitation: "invitationMessage",
  acceptancemessage: "acceptanceMessage",
  acceptance: "acceptanceMessage",
  followup1: "followUp1Message",
  followup1message: "followUp1Message",
  "follow-up1": "followUp1Message",
  followup2: "followUp2Message",
  followup2message: "followUp2Message",
  "follow-up2": "followUp2Message",
  followup3: "followUp3Message",
  followup3message: "followUp3Message",
  "follow-up3": "followUp3Message",
};

export type MappedLeadRow = {
  linkedinUrl: string;
  linkedinApi?: "sales_navigator" | "recruiter" | null;
  email?: string | null;
  firstName: string | null;
  lastName: string | null;
  name: string | null;
  headline: string | null;
  location: string | null;
  profilePictureUrl: string | null;
  companyName?: string | null;
  companyDomain?: string | null;
  companyLinkedinUrl?: string | null;
  campaignId?: string | null;
  campaignName: string | null;
  invitationMessage: string | null;
  acceptanceMessage: string | null;
  followUp1Message: string | null;
  followUp2Message: string | null;
  followUp3Message: string | null;
};

export type SpreadsheetLeadInput = {
  raw: Record<string, string>;
  mapped: MappedLeadRow;
  mappedHeaders?: string[];
  sourceMapping?: LinkedinCsvMapping;
};

export type LinkedinCsvMapping = Partial<Record<keyof Omit<MappedLeadRow, "campaignId" | "campaignName">, string>>;

export function suggestedLinkedinMapping(headers: string[]): LinkedinCsvMapping {
  const result: LinkedinCsvMapping = {};
  for (const header of headers) {
    const field = SPREADSHEET_COLUMN_MAP[normalizeSpreadsheetHeader(header)] as keyof LinkedinCsvMapping | undefined;
    if (field && !result[field]) result[field] = header;
  }
  return result;
}

export function mapSpreadsheetRowsWithMapping(rows: Record<string, string>[], mapping: LinkedinCsvMapping): SpreadsheetLeadInput[] {
  const mappedHeaders = Object.values(mapping).filter((value): value is string => !!value);
  const read = (row: Record<string, string>, field: keyof LinkedinCsvMapping) => {
    const header = mapping[field];
    return header ? String(row[header] ?? "").trim() || null : null;
  };
  return rows.map((raw) => ({
    raw,
    mappedHeaders,
    sourceMapping: { ...mapping },
    mapped: {
      linkedinUrl: read(raw, "linkedinUrl") ?? "",
      linkedinApi: normalizeLinkedinApiHint(read(raw, "linkedinApi")),
      email: read(raw, "email"),
      firstName: read(raw, "firstName"),
      lastName: read(raw, "lastName"),
      name: read(raw, "name"),
      headline: read(raw, "headline"),
      location: read(raw, "location"),
      profilePictureUrl: read(raw, "profilePictureUrl"),
      companyName: read(raw, "companyName"),
      companyDomain: read(raw, "companyDomain"),
      companyLinkedinUrl: read(raw, "companyLinkedinUrl"),
      campaignName: null,
      invitationMessage: read(raw, "invitationMessage"),
      acceptanceMessage: read(raw, "acceptanceMessage"),
      followUp1Message: read(raw, "followUp1Message"),
      followUp2Message: read(raw, "followUp2Message"),
      followUp3Message: read(raw, "followUp3Message"),
    },
  }));
}

export function personRaw(_row: MappedLeadRow, raw: Record<string, string>, explicitlyMapped: string[] = []): Record<string, string> {
  const explicit = new Set(explicitlyMapped);
  const usesExplicitMapping = explicitlyMapped.length > 0;
  const unmappedRaw: Record<string, string> = {};
  for (const [key, value] of Object.entries(raw)) {
      if (explicit.has(key)) continue;
      const mapped = SPREADSHEET_COLUMN_MAP[normalizeSpreadsheetHeader(key)];
      // Legacy imports auto-map every recognized alias. In the reviewed
      // mapping flow, only the headers the user selected are mapped, so a
      // recognized-but-unselected column still belongs in People raw data.
      if (!usesExplicitMapping && mapped) continue;
      unmappedRaw[key] = value;
      const words = key.trim().split(/[^a-zA-Z0-9]+/).filter(Boolean);
      let alias = words.map((word, index) => index === 0 ? word[0]!.toLowerCase() + word.slice(1) : word[0]!.toUpperCase() + word.slice(1)).join("");
      if (/^\d/.test(alias)) alias = `field${alias}`;
      if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key) && alias && !(alias in unmappedRaw)) unmappedRaw[alias] = value;
  }
  return {
    ...unmappedRaw,
    ...(_row.location ? { location: _row.location } : {}),
  };
}

export function mapSpreadsheetRows(rows: Record<string, string>[]): MappedLeadRow[] {
  return rows.map((row) => {
    const out: Record<string, string> = {};
    for (const [key, val] of Object.entries(row)) {
      const field = SPREADSHEET_COLUMN_MAP[normalizeSpreadsheetHeader(key)];
      if (field) out[field] = String(val).trim();
    }
    return {
      linkedinUrl: out.linkedinUrl ?? "",
      linkedinApi: out.linkedinApi === "sales_navigator" || out.linkedinApi === "recruiter" ? out.linkedinApi : null,
      email: out.email || null,
      firstName: out.firstName || null,
      lastName: out.lastName || null,
      name: out.name || null,
      headline: out.headline || null,
      location: out.location || null,
      profilePictureUrl: out.profilePictureUrl || null,
      companyName: out.companyName || null,
      companyDomain: out.companyDomain || null,
      companyLinkedinUrl: out.companyLinkedinUrl || null,
      campaignName: out.campaignName || null,
      invitationMessage: out.invitationMessage || null,
      acceptanceMessage: out.acceptanceMessage || null,
      followUp1Message: out.followUp1Message || null,
      followUp2Message: out.followUp2Message || null,
      followUp3Message: out.followUp3Message || null,
    };
  });
}

export const prepareSpreadsheetImport = (
  rawRows: Record<string, string>[]
): SpreadsheetLeadInput[] => {
  const mapped = mapSpreadsheetRows(rawRows);
  return rawRows.map((raw, index) => ({ raw, mapped: mapped[index]! }));
};

export type ImportLeadsOptions = {
  /** Fixed campaign for all new rows (campaign upload). */
  campaignId?: string | null;
  /** If true, set campaignId on existing leads that have none (campaign upload). */
  attachCampaignToExisting?: boolean;
  /** Original filename, retained in import_runs for audit/replay. */
  filename?: string | null;
};

export type CrossCampaignNotice = {
  linkedinUrl: string;
  name: string | null;
  /** Other campaigns this lead was already contacted under, by a different account. */
  alsoInCampaigns: { id: string; name: string }[];
};

export type ImportLeadsResult = {
  created: number;
  /** Existing leads linked to campaign when attachCampaignToExisting is set. */
  attached: number;
  failed: number;
  /** @deprecated Use `failed` — kept for older clients */
  skipped: number;
  total: number;
  errors: string[];
  failedRows: FailedLeadExportRow[];
  /** Newly created leads that were already contacted elsewhere, for a heads-up (not a failure). */
  crossCampaignNotices: CrossCampaignNotice[];
};

const pushFailure = (
  failedRows: FailedLeadExportRow[],
  errors: string[],
  raw: Record<string, string>,
  reason: string
) => {
  failedRows.push({ raw, reason });
  errors.push(reason);
};

const resolveCampaignIdsByName = async (names: string[]): Promise<Map<string, string>> => {
  const map = new Map<string, string>();
  if (names.length === 0) return map;

  const existing = await db
    .select({ id: campaigns.id, name: campaigns.name })
    .from(campaigns)
    .where(and(inOrg(campaigns), inArray(campaigns.name, names)));
  for (const c of existing) map.set(c.name, c.id);

  const missing = names.filter((n) => !map.has(n));
  if (missing.length > 0) {
    await db
      .insert(campaigns)
      .values(missing.map((name) => ({ name, organizationId: currentOrganizationId(), updatedAt: new Date() })));
    const created = await db
      .select({ id: campaigns.id, name: campaigns.name })
      .from(campaigns)
      .where(and(inOrg(campaigns), inArray(campaigns.name, missing)));
    for (const c of created) map.set(c.name, c.id);
  }

  return map;
};

export const importLeadRows = async (
  inputs: SpreadsheetLeadInput[],
  options: ImportLeadsOptions = {}
): Promise<ImportLeadsResult> => {
  // A search result/export is staging data, not a CRM record. The only
  // supported materialization boundary is explicit enrollment in a campaign.
  if (!options.campaignId) throw new Error(IMPORT_FAILURE.CAMPAIGN_REQUIRED);
  const errors: string[] = [];
  const failedRows: FailedLeadExportRow[] = [];
  const fixedCampaignId = options.campaignId;
  const [ownCampaign] = await db
    .select({ id: campaigns.id })
    .from(campaigns)
    .where(and(inOrg(campaigns), eq(campaigns.id, fixedCampaignId)))
    .limit(1);
  if (!ownCampaign) throw new Error("Campaign not found");
  const { attachCampaignToExisting = false } = options;

  const parsed: { sourceIdentifier: string; sourceApi: LinkedinApiHint | null; sourceKey: string; row: MappedLeadRow; raw: Record<string, string>; mappedHeaders: string[] }[] = [];
  const seenSources = new Set<string>();
  const sourceByEmail = new Map<string, string>();

  for (const { raw, mapped: row, mappedHeaders = [] } of inputs) {
    if (!row.linkedinUrl) {
      pushFailure(failedRows, errors, raw, IMPORT_FAILURE.MISSING_URL);
      continue;
    }
    const sourceIdentifier = normalizeLinkedinSourceIdentifier(row.linkedinUrl);
    if (!sourceIdentifier) {
      pushFailure(failedRows, errors, raw, IMPORT_FAILURE.INVALID_URL);
      continue;
    }
    const sourceApi = normalizeLinkedinApiHint(row.linkedinApi) ?? inferLinkedinApi(sourceIdentifier);
    const sourceKey = linkedinSourceIdentityKey(sourceIdentifier, sourceApi)!;
    const email = row.email ? normalizeEmail(row.email) : null;
    if (row.email && !email) {
      pushFailure(failedRows, errors, raw, IMPORT_FAILURE.INVALID_EMAIL);
      continue;
    }
    if (email) {
      const priorSource = sourceByEmail.get(email);
      if (priorSource && priorSource !== sourceKey) {
        pushFailure(failedRows, errors, raw, IMPORT_FAILURE.EMAIL_IDENTITY_CONFLICT);
        continue;
      }
      sourceByEmail.set(email, sourceKey);
    }
    if (seenSources.has(sourceKey)) {
      pushFailure(failedRows, errors, raw, IMPORT_FAILURE.DUPLICATE_IN_FILE);
      continue;
    }
    if (isInvitationMessageTooLong(row.invitationMessage)) {
      pushFailure(
        failedRows,
        errors,
        raw,
        IMPORT_FAILURE.INVITATION_TOO_LONG(invitationMessageLength(row.invitationMessage))
      );
      continue;
    }
    seenSources.add(sourceKey);
    parsed.push({ sourceIdentifier, sourceApi, sourceKey, row: { ...row, email }, raw, mappedHeaders });
  }

  if (parsed.length === 0) {
    return {
      created: 0,
      attached: 0,
      failed: failedRows.length,
      skipped: failedRows.length,
      total: inputs.length,
      errors,
      failedRows,
      crossCampaignNotices: [],
    };
  }

  // Resolve each row's target campaignId up front — the existence check and the
  // cross-account guard below are both scoped per campaign, so campaignId must
  // be known before either can run.
  let campaignByName = new Map<string, string>();
  const namesToResolve = [
    ...new Set(
      parsed
        .filter((p) => !p.row.campaignId && !fixedCampaignId && p.row.campaignName)
        .map((p) => p.row.campaignName as string)
    ),
  ];
  if (namesToResolve.length > 0) {
    campaignByName = await resolveCampaignIdsByName(namesToResolve);
  }

  const withCampaign = parsed.map((p) => ({
    ...p,
    campaignId:
      p.row.campaignId ??
      fixedCampaignId ??
      (p.row.campaignName ? campaignByName.get(p.row.campaignName) ?? null : null),
  }));

  const sources = withCampaign.map((p) => p.sourceIdentifier);
  const emails = withCampaign.flatMap((p) => p.row.email ? [p.row.email] : []);
  const existingLeads = await db
    .select({
      id: leads.id,
      personId: leads.personId,
      providerId: leads.providerId,
      sourceLinkedinIdentifier: leads.sourceLinkedinIdentifier,
      sourceLinkedinApi: leads.sourceLinkedinApi,
      linkedinUrl: people.linkedinUrl,
      email: people.email,
      campaignId: leads.campaignId,
      status: leads.status,
      campaign: { id: campaigns.id, name: campaigns.name },
    })
    .from(leads)
    .leftJoin(people, eq(leads.personId, people.id))
    .leftJoin(campaigns, eq(leads.campaignId, campaigns.id))
    .where(and(
      inOrg(leads),
      or(
        inArray(leads.sourceLinkedinIdentifier, sources),
        emails.length ? inArray(sql`lower(${people.email})`, emails) : undefined,
      ),
    ));
  // Same-campaign dedup key: a lead already exists in the exact campaign being imported into.
  const campaignKey = (identity: string, campaignId: string | null) => `${identity.toLowerCase()}::${campaignId ?? ""}`;
  const existingByCampaignKey = new Map<string, (typeof existingLeads)[number]>();
  const personIdBySource = new Map<string, string>();
  const personIdByEmail = new Map<string, string>();
  for (const lead of existingLeads) {
    const existingSourceKey = linkedinSourceIdentityKey(lead.sourceLinkedinIdentifier, lead.sourceLinkedinApi);
    if (existingSourceKey) existingByCampaignKey.set(campaignKey(existingSourceKey, lead.campaignId), lead);
    if (lead.email) existingByCampaignKey.set(campaignKey(`email:${lead.email}`, lead.campaignId), lead);
    if (existingSourceKey) personIdBySource.set(existingSourceKey, lead.personId);
    if (lead.email) personIdByEmail.set(lead.email.toLowerCase(), lead.personId);
  }
  // Cross-campaign lookup: every other campaign this linkedinUrl was already contacted
  // (status != PENDING) under, regardless of which account sent it. Surfaced as a
  // heads-up on the newly created lead rather than blocking the import.
  const contactedCampaignsByIdentity = new Map<string, Map<string, { id: string; name: string }>>();
  for (const l of existingLeads) {
    if (!l.campaign || l.status === "PENDING") continue;
    for (const key of [
      linkedinSourceIdentityKey(l.sourceLinkedinIdentifier, l.sourceLinkedinApi),
      l.email ? `email:${l.email.toLowerCase()}` : null,
    ].filter((value): value is string => !!value)) {
      const map = contactedCampaignsByIdentity.get(key) ?? new Map<string, { id: string; name: string }>();
      map.set(l.campaign.id, l.campaign);
      contactedCampaignsByIdentity.set(key, map);
    }
  }

  const unassignedBySource = new Map(
    existingLeads
      .filter((lead) => lead.campaignId === null && lead.sourceLinkedinIdentifier)
      .map((lead) => [linkedinSourceIdentityKey(lead.sourceLinkedinIdentifier, lead.sourceLinkedinApi)!, lead]),
  );
  const leadsToAttach = new Map<string, {
    lead: (typeof existingLeads)[number];
    incoming: (typeof withCampaign)[number];
  }>();
  const leadsToRefresh: {
    lead: (typeof existingLeads)[number];
    incoming: (typeof withCampaign)[number];
  }[] = [];

  const toCreate: (typeof withCampaign) = [];
  const crossCampaignNotices: CrossCampaignNotice[] = [];
  for (const p of withCampaign) {
    const existing = existingByCampaignKey.get(campaignKey(p.sourceKey, p.campaignId))
      ?? (p.row.email ? existingByCampaignKey.get(campaignKey(`email:${p.row.email}`, p.campaignId)) : undefined);
    if (existing) {
      pushFailure(failedRows, errors, p.raw, IMPORT_FAILURE.ALREADY_EXISTS);
      leadsToRefresh.push({ lead: existing, incoming: p });
      continue;
    }

    const unassigned = attachCampaignToExisting && fixedCampaignId
      ? unassignedBySource.get(p.sourceKey)
      : undefined;
    if (unassigned) {
      leadsToAttach.set(unassigned.id, { lead: unassigned, incoming: p });
      continue;
    }

    const otherCampaigns = contactedCampaignsByIdentity.get(p.sourceKey)
      ?? (p.row.email ? contactedCampaignsByIdentity.get(`email:${p.row.email}`) : undefined);
    if (otherCampaigns && otherCampaigns.size > 0) {
      crossCampaignNotices.push({
        linkedinUrl: p.sourceIdentifier,
        name: p.row.name,
        alsoInCampaigns: [...otherCampaigns.values()].filter((c) => c.id !== p.campaignId),
      });
    }

    toCreate.push(p);
  }

  let created = 0;
  const attached = leadsToAttach.size;
  const existingRowsToRefresh = [...leadsToAttach.values(), ...leadsToRefresh];
  await withLeadTransaction(async (tx) => {
    // A spreadsheet commonly contains hundreds of people from only a handful
    // of companies. Reuse company rows within this transaction instead of
    // locking, selecting, and updating the same company for every lead.
    // Lock and load existing People once as well, so their cached snapshots
    // remain safe to merge throughout this transaction.
    const personIdsToRefresh = [...new Set(existingRowsToRefresh.map(({ lead }) => lead.personId))];
    const lockedPeople = personIdsToRefresh.length
      ? await tx
          .select()
          .from(people)
          .where(and(inOrg(people), inArray(people.id, personIdsToRefresh)))
          .orderBy(people.id)
          .for("update")
      : [];
    const mutationContext: LeadMutationContext = {
      companyCache: new Map(),
      personCache: new Map(lockedPeople.map((person) => [person.id, person])),
    };
    const campaignMessages = Object.fromEntries([
      "invitationMessage", "acceptanceMessage", "followUp1Message", "followUp2Message", "followUp3Message",
    ].flatMap((field) => {
      const values = [...new Set(withCampaign.map((item) => item.row[field as keyof MappedLeadRow]).filter((value): value is string => typeof value === "string" && value.length > 0))];
      if (values.length > 1) throw new Error(`${field} must be the same for every row because message templates belong to the campaign`);
      return values.length ? [[field, values[0]]] : [];
    }));
    if (Object.keys(campaignMessages).length) {
      await tx.update(campaigns).set({ ...campaignMessages, updatedAt: new Date() }).where(and(inOrg(campaigns), eq(campaigns.id, fixedCampaignId)));
    }
    if (leadsToAttach.size > 0 && fixedCampaignId) {
      await tx
        .update(leads)
        .set({ campaignId: fixedCampaignId })
        .where(and(inOrg(leads), inArray(leads.id, [...leadsToAttach.keys()])));

    }

    // A duplicate enrollment is not a duplicate Person update. Refresh the
    // canonical record with newly mapped/enriched values and retain the one
    // existing campaign Lead row.
    for (const { lead, incoming } of existingRowsToRefresh) {
      const person = await enrichPersonById(tx, lead.personId, {
        email: incoming.row.email ?? lead.email,
        linkedinUrl: lead.linkedinUrl,
        firstName: incoming.row.firstName,
        lastName: incoming.row.lastName,
        fullName: incoming.row.name,
        title: incoming.row.headline,
        company: incoming.row.companyDomain || incoming.row.companyName
          ? { domain: incoming.row.companyDomain, name: incoming.row.companyName, linkedinUrl: incoming.row.companyLinkedinUrl }
          : null,
        raw: personRaw(incoming.row, incoming.raw, incoming.mappedHeaders),
        source: `campaign:linkedin:${incoming.campaignId ?? "unassigned"}`,
      }, mutationContext);
      await tx.update(leads).set({
        personId: person.id,
        ...(lead.providerId ? {} : {
          sourceLinkedinIdentifier: incoming.sourceIdentifier,
          sourceLinkedinApi: incoming.sourceApi,
        }),
      }).where(and(inOrg(leads), eq(leads.id, lead.id)));
    }

    // Serialize all source identities once per batch, then re-read ownership in
    // bulk. Every importer uses this same advisory-lock namespace, so this
    // retains the concurrent-import guarantee without one lock + SELECT round
    // trip for every row.
    const sourceRowsByKey = new Map<string, { personId: string; campaignId: string | null }[]>();
    const sourceIdentifiers = [...new Set(toCreate.map((item) => item.sourceIdentifier.toLowerCase()))];
    const sourceLockKeys = [...new Set(toCreate.map((item) => item.sourceKey))].sort();
    for (const batch of chunkArray(sourceLockKeys, IMPORT_BATCH_SIZE)) {
      await tx.execute(advisoryLockStatement(batch));
    }
    for (const batch of chunkArray(sourceIdentifiers, IMPORT_BATCH_SIZE)) {
      const rows = await tx
        .select({
          sourceLinkedinIdentifier: leads.sourceLinkedinIdentifier,
          sourceLinkedinApi: leads.sourceLinkedinApi,
          personId: leads.personId,
          campaignId: leads.campaignId,
        })
        .from(leads)
        .where(and(inOrg(leads), sql`lower(${leads.sourceLinkedinIdentifier}) IN (${sql.join(batch.map((value) => sql`${value}`), sql`, `)})`));
      for (const row of rows) {
        const key = linkedinSourceIdentityKey(row.sourceLinkedinIdentifier, row.sourceLinkedinApi);
        if (key) {
          const matches = sourceRowsByKey.get(key) ?? [];
          matches.push({ personId: row.personId, campaignId: row.campaignId });
          sourceRowsByKey.set(key, matches);
        }
      }
    }

    const fallbackToCreate: typeof toCreate = [];
    const provisionalToCreate: typeof toCreate = [];
    const eligibleToCreate: typeof toCreate = [];
    for (const item of toCreate) {
      const sourceMatches = sourceRowsByKey.get(item.sourceKey) ?? [];
      const sourcePersonIds = new Set(sourceMatches.map((match) => match.personId));
      if (sourcePersonIds.size > 1) {
        throw new Error("This unresolved LinkedIn source already belongs to multiple people");
      }
      if (sourceMatches.some((match) => match.campaignId === item.campaignId)) {
        pushFailure(failedRows, errors, item.raw, IMPORT_FAILURE.ALREADY_EXISTS);
        continue;
      }

      // Rows with an email or an already-known Person still need the canonical
      // upsert/enrichment path. Only source-only rows with no owner can safely
      // use the set-based provisional insert below.
      const knownPersonId = sourceMatches[0]?.personId
        ?? personIdBySource.get(item.sourceKey)
        ?? (item.row.email ? personIdByEmail.get(item.row.email) : undefined);
      eligibleToCreate.push(item);
      if (knownPersonId || item.row.email) fallbackToCreate.push(item);
      else provisionalToCreate.push(item);
    }

    // Pre-claim email identities used by fallback rows in the same stable
    // order as upsertPerson(). This avoids an import holding one email lock
    // while another import is holding a different one and waiting on it.
    const fallbackEmailKeys = [...new Set(
      fallbackToCreate
        .map((item) => item.row.email ? `person:email:${item.row.email}` : null)
        .filter((value): value is string => !!value),
    )].sort();
    for (const batch of chunkArray(fallbackEmailKeys, IMPORT_BATCH_SIZE)) {
      await tx.execute(advisoryLockStatement(batch));
    }

    // Company identity is independent of Person identity. Prepare the distinct
    // domains once so bulk-created People retain createProvisionalPerson's
    // company reuse/update semantics without one company lookup per lead.
    const desiredCompanies = new Map<string, { name: string | null; linkedinUrl: string | null; source: string }>();
    for (const item of eligibleToCreate) {
      const domain = normalizeCompanyDomain(item.row.companyDomain);
      if (!domain) continue;
      const current = desiredCompanies.get(domain) ?? {
        name: null,
        linkedinUrl: null,
        source: `campaign:linkedin:${item.campaignId ?? "unassigned"}`,
      };
      const name = item.row.companyName?.trim() || null;
      if (name) current.name = name;
      // Last non-empty value wins, matching how the name is folded above: rows
      // for one domain disagree far less often than they leave the cell blank.
      const linkedinUrl = item.row.companyLinkedinUrl?.trim() || null;
      if (linkedinUrl) current.linkedinUrl = linkedinUrl;
      desiredCompanies.set(domain, current);
    }
    const companyCache = mutationContext.companyCache ?? new Map();
    mutationContext.companyCache = companyCache;
    const companyDomains = [...desiredCompanies.keys()].sort();
    // The prefix belongs in the value, not the statement: sql`company:${domain}`
    // emits the literal text into the SQL and leaves `company:$1`, which the
    // server rejects. upsertCompany() locks the same `company:<domain>` key.
    const companyLockKeys = companyDomains.map((domain) => `company:${domain}`);
    for (const batch of chunkArray(companyLockKeys, IMPORT_BATCH_SIZE)) {
      await tx.execute(advisoryLockStatement(batch));
    }
    for (const batch of chunkArray(companyDomains, IMPORT_BATCH_SIZE)) {
      const existing = await tx.select().from(companies).where(and(inOrg(companies), inArray(companies.domain, batch))).for("update");
      for (const company of existing) companyCache.set(company.domain, company);
    }
    const missingCompanies = companyDomains.filter((domain) => !companyCache.has(domain));
    for (const batch of chunkArray(missingCompanies, IMPORT_BATCH_SIZE)) {
      if (!batch.length) continue;
      await tx.insert(companies).values(batch.map((domain) => ({
        id: randomUUID(),
        organizationId: currentOrganizationId(),
        domain,
        name: desiredCompanies.get(domain)!.name,
        linkedinUrl: desiredCompanies.get(domain)!.linkedinUrl,
        raw: {},
        source: desiredCompanies.get(domain)!.source,
      }))).onConflictDoNothing();
    }
    for (const batch of chunkArray(companyDomains, IMPORT_BATCH_SIZE)) {
      const rows = await tx.select().from(companies).where(and(inOrg(companies), inArray(companies.domain, batch))).for("update");
      for (const company of rows) {
        const desired = desiredCompanies.get(company.domain);
        const nextName = desired?.name && desired.name !== company.name ? desired.name : null;
        // Only fills a blank. An existing company LinkedIn URL is a stronger
        // record than a spreadsheet cell, and overwriting it would let one
        // import rewrite the profile link for every lead sharing the domain.
        const nextLinkedinUrl = desired?.linkedinUrl && !company.linkedinUrl ? desired.linkedinUrl : null;
        if (nextName || nextLinkedinUrl) {
          const [updated] = await tx.update(companies).set({
            ...(nextName ? { name: nextName } : {}),
            ...(nextLinkedinUrl ? { linkedinUrl: nextLinkedinUrl } : {}),
            updatedAt: new Date(),
          }).where(and(inOrg(companies), eq(companies.id, company.id))).returning();
          companyCache.set(company.domain, updated);
        } else {
          companyCache.set(company.domain, company);
        }
      }
    }

    // New source-only rows have no existing Person identity to merge with, so
    // they can be inserted in batches. Explicit IDs make the returned mapping
    // deterministic and let the following Lead insert avoid positional
    // assumptions about INSERT ... RETURNING ordering.
    const provisionalPeople = provisionalToCreate.map((item) => {
      const companyDomain = normalizeCompanyDomain(item.row.companyDomain);
      const company = companyDomain ? companyCache.get(companyDomain) : null;
      const names = resolvePersonNames({
        firstName: item.row.firstName,
        lastName: item.row.lastName,
        fullName: item.row.name,
      });
      const hasCompanyInput = Boolean(item.row.companyDomain || item.row.companyName);
      return {
        item,
        person: {
          organizationId: currentOrganizationId(),
          id: randomUUID(),
          email: null,
          linkedinUrl: null,
          ...names,
          title: item.row.headline?.trim() || null,
          profilePictureUrl: item.row.profilePictureUrl?.trim() || null,
          companyId: company?.id ?? null,
          raw: {
            ...personRaw(item.row, item.raw, item.mappedHeaders),
            ...(!company && item.row.companyName?.trim() ? { company: item.row.companyName.trim(), companyName: item.row.companyName.trim() } : {}),
            ...(!company && hasCompanyInput && item.row.companyDomain ? { companyDomain: normalizeCompanyDomain(item.row.companyDomain) } : {}),
          },
          source: `campaign:linkedin:${item.campaignId ?? "unassigned"}`,
        },
      };
    });
    for (const batch of chunkArray(provisionalPeople, IMPORT_BATCH_SIZE)) {
      if (!batch.length) continue;
      await tx.insert(people).values(batch.map(({ person }) => person));
      const leadRows = await tx.insert(leads).values(batch.map(({ item, person }) => ({
        organizationId: currentOrganizationId(),
        personId: person.id,
        sourceLinkedinIdentifier: item.sourceIdentifier,
        sourceLinkedinApi: item.sourceApi,
        campaignId: item.campaignId,
        updatedAt: new Date(),
      }))).onConflictDoNothing().returning({
        id: leads.id,
        sourceLinkedinIdentifier: leads.sourceLinkedinIdentifier,
        sourceLinkedinApi: leads.sourceLinkedinApi,
      });
      const insertedSources = new Set(leadRows.map((row) => linkedinSourceIdentityKey(row.sourceLinkedinIdentifier, row.sourceLinkedinApi)));
      const orphanedPersonIds: string[] = [];
      for (const { item, person } of batch) {
        if (!insertedSources.has(item.sourceKey)) {
          pushFailure(failedRows, errors, item.raw, IMPORT_FAILURE.ALREADY_EXISTS);
          orphanedPersonIds.push(person.id);
          continue;
        }
        personIdBySource.set(item.sourceKey, person.id);
        created += 1;
      }
      if (orphanedPersonIds.length) {
        await tx.delete(people).where(and(inOrg(people), inArray(people.id, orphanedPersonIds)));
      }
    }

    // Existing identities, email-backed rows, and any collision fallback retain
    // the canonical enrich/upsert path. The source locks and bulk re-read above
    // make the old per-row source SELECT unnecessary.
    for (const item of fallbackToCreate) {
      const sourceMatches = sourceRowsByKey.get(item.sourceKey) ?? [];
      const personInput = {
        email: item.row.email,
        firstName: item.row.firstName,
        lastName: item.row.lastName,
        fullName: item.row.name,
        title: item.row.headline,
        profilePictureUrl: item.row.profilePictureUrl,
        company: item.row.companyDomain || item.row.companyName
          ? { domain: item.row.companyDomain, name: item.row.companyName, linkedinUrl: item.row.companyLinkedinUrl }
          : null,
        raw: personRaw(item.row, item.raw, item.mappedHeaders),
        source: `campaign:linkedin:${item.campaignId ?? "unassigned"}`,
      };
      const knownPersonId = sourceMatches[0]?.personId
        ?? personIdBySource.get(item.sourceKey)
        ?? (item.row.email ? personIdByEmail.get(item.row.email) : undefined);
      const person = knownPersonId
        ? await enrichPersonById(tx, knownPersonId, personInput, mutationContext)
        : await upsertPerson(tx, personInput, mutationContext);
      personIdBySource.set(item.sourceKey, person.id);
      if (item.row.email) personIdByEmail.set(item.row.email, person.id);
      const [nativeLead] = await tx
        .insert(leads)
        .values({
          organizationId: currentOrganizationId(),
          personId: person.id,
          sourceLinkedinIdentifier: item.sourceIdentifier,
          sourceLinkedinApi: item.sourceApi,
          campaignId: item.campaignId,
          updatedAt: new Date(),
        })
        .onConflictDoNothing()
        .returning({ id: leads.id });
      if (!nativeLead) {
        pushFailure(failedRows, errors, item.raw, IMPORT_FAILURE.ALREADY_EXISTS);
        continue;
      }
      created += 1;
    }

    // Fallback rows may have shared a company domain with a bulk row. Restore
    // the same last-non-empty-name-wins result that the old row-ordered
    // upsertCompany loop produced after both paths have run.
    for (const batch of chunkArray(companyDomains, IMPORT_BATCH_SIZE)) {
      for (const domain of batch) {
        const desired = desiredCompanies.get(domain);
        const current = companyCache.get(domain);
        if (!desired?.name || !current || desired.name === current.name) continue;
        const [updated] = await tx.update(companies)
          .set({ name: desired.name, updatedAt: new Date() })
          .where(and(inOrg(companies), eq(companies.id, current.id)))
          .returning();
        companyCache.set(domain, updated);
      }
    }

    await tx.insert(importRuns).values({
      organizationId: currentOrganizationId(),
      source: "file",
      filename: options.filename ?? null,
      destination: "campaign",
      destinationCampaignId: fixedCampaignId,
      mapping: {
        channel: "linkedin",
        fields: inputs[0]?.sourceMapping ?? null,
        unmapped: "people.raw",
      },
      stats: { total: inputs.length, created, attached, failed: failedRows.length },
    });
  });

  const failed = failedRows.length;

  return {
    created,
    attached,
    failed,
    skipped: failed,
    total: inputs.length,
    errors,
    failedRows,
    crossCampaignNotices,
  };
};

/** Import from parsed spreadsheet rows (raw + mapped). */
export const importSpreadsheetLeads = (
  rawRows: Record<string, string>[],
  options: ImportLeadsOptions = {}
): Promise<ImportLeadsResult> => importLeadRows(prepareSpreadsheetImport(rawRows), options);

/** Import from mapped rows only (JSON API) — builds synthetic raw rows for failed export. */
export const importLeads = (
  rows: MappedLeadRow[],
  options: ImportLeadsOptions = {}
): Promise<ImportLeadsResult> =>
  importLeadRows(
    rows.map((mapped) => ({ raw: mappedLeadRowToRaw(mapped), mapped })),
    options
  );
