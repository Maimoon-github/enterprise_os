import { and, eq, sql, type SQL } from "drizzle-orm";
import { leads } from "@/lib/linkedin/schema";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";
import type { LeadStatus } from "@/lib/linkedin/schema";

export type LeadListFilters = {
  status?: string;
  search?: string;
  accountId?: string;
  campaignId?: string;
};

export const buildLeadWhere = (filters: LeadListFilters): SQL | undefined => {
  const search = filters.search?.trim() ?? "";
  const conditions: SQL[] = [inOrg(leads)];

  if (filters.campaignId) conditions.push(eq(leads.campaignId, filters.campaignId));
  if (filters.status) conditions.push(eq(leads.status, filters.status as LeadStatus));
  if (filters.accountId) conditions.push(eq(leads.linkedinAccountId, filters.accountId));
  if (search) {
    conditions.push(sql`(
      ${leads.sourceLinkedinIdentifier} ilike ${`%${search}%`}
      or ${leads.name} ilike ${`%${search}%`}
      or exists (
      select 1 from people p
      left join companies c on c.id = p.company_id and c.organization_id = ${currentOrganizationId()}
      where p.id = ${leads.personId}
        and p.organization_id = ${currentOrganizationId()}
        and (
          p.linkedin_url ilike ${`%${search}%`}
          or p.email ilike ${`%${search}%`}
          or p.first_name ilike ${`%${search}%`}
          or p.last_name ilike ${`%${search}%`}
          or p.full_name ilike ${`%${search}%`}
          or p.title ilike ${`%${search}%`}
          or p.raw::text ilike ${`%${search}%`}
          or c.name ilike ${`%${search}%`}
          or c.domain ilike ${`%${search}%`}
        )
      )
    )`);
  }

  return and(...conditions);
};
