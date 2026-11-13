import { and, eq, inArray, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { gridColumns, gridRows, gridTables } from "@/lib/grid/schema";
import { campaigns as linkedinCampaigns, leads as linkedinLeads } from "@/lib/linkedin/schema";
import { outreachCampaigns, outreachLeads, suppressionList } from "@/lib/outreach/schema";
import { inferLinkedinApi, linkedinSourceIdentityKey, normalizeEmail, normalizeLinkedinSourceIdentifier } from "./identity";
import { importRuns } from "./schema";
import { createProvisionalPerson, enrichPersonById, upsertPerson, withLeadTransaction } from "./records";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";

export type GridCampaignChannel = "email" | "linkedin";

export type GridCampaignMapping = Partial<Record<
  | "email"
  | "linkedinUrl"
  | "firstName"
  | "lastName"
  | "fullName"
  | "title"
  | "companyName"
  | "companyDomain"
  | "invitationMessage"
  | "acceptanceMessage"
  | "followUp1Message"
  | "followUp2Message"
  | "followUp3Message",
  string
>>;

export type CreateGridCampaignInput = {
  tableId: string;
  channel: GridCampaignChannel;
  name: string;
  rowIds: string[];
  mapping: GridCampaignMapping;
};

export type GridCampaignFailure = { rowId: string; error: string };

const CHANNEL_TEMPLATE_FIELDS = new Set([
  "invitationMessage",
  "acceptanceMessage",
  "followUp1Message",
  "followUp2Message",
  "followUp3Message",
]);

function stringCell(cells: Record<string, unknown>, key?: string): string | null {
  if (!key) return null;
  const value = cells[key];
  if (value === null || value === undefined) return null;
  const text = typeof value === "string" ? value.trim() : String(value).trim();
  return text || null;
}

/** Produces a token-safe alias while retaining the displayed source name. */
export function templateVariableKey(label: string): string {
  const words = label.trim().split(/[^a-zA-Z0-9]+/).filter(Boolean);
  if (!words.length) return "";
  const key = words
    .map((word, index) => index === 0
      ? word[0]!.toLowerCase() + word.slice(1)
      : word[0]!.toUpperCase() + word.slice(1))
    .join("");
  return /^\d/.test(key) ? `field${key}` : key;
}

export function gridRowToPersonInput(
  cells: Record<string, unknown>,
  columns: { key: string; name: string }[],
  mapping: GridCampaignMapping,
) {
  const mappedKeys = new Set(Object.values(mapping).filter(Boolean));
  const raw: Record<string, unknown> = {};
  for (const column of columns) {
    if (mappedKeys.has(column.key) || !(column.key in cells)) continue;
    const value = cells[column.key];
    raw[column.name] = value;
    const alias = templateVariableKey(column.name);
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(column.name) && alias && !(alias in raw)) raw[alias] = value;
  }

  return {
    email: stringCell(cells, mapping.email),
    linkedinUrl: stringCell(cells, mapping.linkedinUrl),
    firstName: stringCell(cells, mapping.firstName),
    lastName: stringCell(cells, mapping.lastName),
    fullName: stringCell(cells, mapping.fullName),
    title: stringCell(cells, mapping.title),
    company: {
      name: stringCell(cells, mapping.companyName),
      domain: stringCell(cells, mapping.companyDomain),
    },
    raw,
  };
}

export async function createCampaignFromGrid(input: CreateGridCampaignInput) {
  const name = input.name.trim();
  if (!name) throw new Error("Campaign name is required");
  if (!input.rowIds.length) throw new Error("Select at least one row");
  const required = input.channel === "email" ? input.mapping.email : input.mapping.linkedinUrl;
  if (!required) throw new Error(`Map a${input.channel === "email" ? "n Email" : " LinkedIn URL"} column`);

  // grid_columns / grid_rows inherit their scope from the table: prove the
  // table is this organization's before reading either.
  const [ownTable] = await db.select({ id: gridTables.id }).from(gridTables).where(and(inOrg(gridTables), eq(gridTables.id, input.tableId))).limit(1);
  if (!ownTable) throw new Error("Table not found");

  const [columns, rows] = await Promise.all([
    db.select({ key: gridColumns.key, name: gridColumns.name }).from(gridColumns).where(eq(gridColumns.tableId, input.tableId)),
    db.select({ id: gridRows.id, cells: gridRows.cells }).from(gridRows).where(and(eq(gridRows.tableId, input.tableId), inArray(gridRows.id, [...new Set(input.rowIds)]))),
  ]);
  if (rows.length !== new Set(input.rowIds).size) throw new Error("One or more selected rows do not belong to this table");
  const knownKeys = new Set(columns.map((column) => column.key));
  for (const key of Object.values(input.mapping)) {
    if (key && !knownKeys.has(key)) throw new Error("The mapping contains a column that no longer exists");
  }

  const failures: GridCampaignFailure[] = [];
  const prepared = rows.flatMap((row) => {
    const person = gridRowToPersonInput(row.cells ?? {}, columns, input.mapping);
    const email = normalizeEmail(person.email);
    const linkedinUrl = normalizeLinkedinSourceIdentifier(person.linkedinUrl);
    if (input.channel === "email" && !email) {
      failures.push({ rowId: row.id, error: "Missing or invalid email" });
      return [];
    }
    if (input.channel === "linkedin" && !linkedinUrl) {
      failures.push({ rowId: row.id, error: "Missing or invalid LinkedIn URL" });
      return [];
    }
    return [{ row, person: { ...person, email, linkedinUrl } }];
  });
  if (!prepared.length) throw new Error("None of the selected rows has a valid mapped destination");

  return withLeadTransaction(async (tx) => {
    let campaignId: string;
    if (input.channel === "email") {
      const [campaign] = await tx.insert(outreachCampaigns).values({ organizationId: currentOrganizationId(), name, status: "draft", sequence: [] }).returning({ id: outreachCampaigns.id });
      campaignId = campaign.id;
    } else {
      const campaignMessages = Object.fromEntries([...CHANNEL_TEMPLATE_FIELDS].map((field) => {
        const values = [...new Set(prepared.map((item) => stringCell(item.row.cells ?? {}, input.mapping[field as keyof GridCampaignMapping])).filter(Boolean))];
        if (values.length > 1) throw new Error(`${field} must use one campaign-wide template, but the selected rows contain different values`);
        return [field, values[0] ?? null];
      })) as Record<string, string | null>;
      // Grid-created campaigns need account assignment/review before sending.
      const [campaign] = await tx.insert(linkedinCampaigns).values({ organizationId: currentOrganizationId(), name, status: "PAUSED", ...campaignMessages, updatedAt: new Date() }).returning({ id: linkedinCampaigns.id });
      campaignId = campaign.id;
    }

    const suppressed = input.channel === "email"
      ? new Set((await tx.select({ email: suppressionList.email }).from(suppressionList).where(and(inOrg(suppressionList), inArray(suppressionList.email, prepared.map((item) => item.person.email!))))).map((item) => item.email))
      : new Set<string>();
    let created = 0;
    for (const item of prepared) {
      if (item.person.email && suppressed.has(item.person.email)) {
        failures.push({ rowId: item.row.id, error: "Email is suppressed" });
        continue;
      }
      try {
        if (input.channel === "email") {
          const person = await upsertPerson(tx, {
            ...item.person,
            company: item.person.company.name || item.person.company.domain ? item.person.company : null,
            source: `grid:${input.tableId}:campaign:${input.channel}:${campaignId}`,
          });
          const [lead] = await tx.insert(outreachLeads).values({ personId: person.id, campaignId }).onConflictDoNothing().returning({ id: outreachLeads.id });
          if (!lead) failures.push({ rowId: item.row.id, error: "Person is already in this campaign" });
          else created += 1;
        } else {
          // The Person and all uploaded profile data exist immediately. Only
          // the unverified LinkedIn identifier remains on the campaign Lead.
          const sourceApi = inferLinkedinApi(item.person.linkedinUrl);
          const sourceKey = linkedinSourceIdentityKey(item.person.linkedinUrl, sourceApi)!;
          await tx.execute(sql`select pg_advisory_xact_lock(hashtextextended(${sourceKey}, 0))`);
          const knownRows = await tx.select({ personId: linkedinLeads.personId })
            .from(linkedinLeads)
            .where(and(
              inOrg(linkedinLeads),
              sql`lower(${linkedinLeads.sourceLinkedinIdentifier}) = lower(${item.person.linkedinUrl!})`,
              sql`${linkedinLeads.sourceLinkedinApi} is not distinct from ${sourceApi}`,
            ))
            .limit(2);
          const knownPersonIds = new Set(knownRows.map((row) => row.personId));
          if (knownPersonIds.size > 1) {
            throw new Error("This unresolved LinkedIn source already belongs to multiple people");
          }
          const known = knownRows[0];
          const personInput = {
            ...item.person,
            linkedinUrl: null,
            company: item.person.company.name || item.person.company.domain ? item.person.company : null,
            source: `grid:${input.tableId}:campaign:${input.channel}:${campaignId}`,
          };
          const person = known
            ? await enrichPersonById(tx, known.personId, personInput)
            : item.person.email
              ? await upsertPerson(tx, personInput)
              : await createProvisionalPerson(tx, personInput);
          const [lead] = await tx.insert(linkedinLeads).values({
            organizationId: currentOrganizationId(),
            personId: person.id,
            campaignId,
            sourceLinkedinIdentifier: item.person.linkedinUrl,
            sourceLinkedinApi: sourceApi,
            updatedAt: new Date(),
          }).onConflictDoNothing().returning({ id: linkedinLeads.id });
          if (!lead) failures.push({ rowId: item.row.id, error: "Person is already in this campaign" });
          else created += 1;
        }
      } catch (error) {
        failures.push({ rowId: item.row.id, error: error instanceof Error ? error.message : String(error) });
      }
    }

    await tx.insert(importRuns).values({
      organizationId: currentOrganizationId(),
      source: "grid",
      gridTableId: input.tableId,
      destination: "campaign",
      destinationCampaignId: campaignId,
      mapping: { channel: input.channel, fields: input.mapping, unmapped: "people.raw" },
      stats: { selected: rows.length, created, failed: failures.length },
    });
    return { campaignId, channel: input.channel, created, failed: failures.length, failures };
  });
}
