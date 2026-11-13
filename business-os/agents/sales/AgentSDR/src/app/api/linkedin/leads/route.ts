import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { count, desc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { campaigns, leads, linkedInAccounts } from "@/lib/linkedin/schema";
import { IMPORT_FAILURE } from "@/lib/linkedin/importLeads";
import { buildLeadWhere } from "@/lib/linkedin/leadListFilters";
import { listCampaignLeadsPage } from "@/lib/linkedin/campaignLeads";
import { companies, people } from "@/lib/leads/schema";
import { personProfile } from "@/lib/leads/variables";

export async function GET(req: NextRequest) {
  return withLinkedinOrg(req, async () => {
    const { searchParams } = new URL(req.url);
    const rawPage = Number(searchParams.get("page") ?? 1);
    const rawLimit = Number(searchParams.get("limit") ?? 20);
    const page = Number.isFinite(rawPage) ? Math.max(1, Math.floor(rawPage)) : 1;
    const limit = Number.isFinite(rawLimit) ? Math.min(100, Math.max(1, Math.floor(rawLimit))) : 20;
    const statusParam = searchParams.get("status");
    const search = searchParams.get("search")?.trim() ?? "";
    const accountId = searchParams.get("accountId") ?? "";
    const campaignId = searchParams.get("campaignId") ?? "";

    try {
      if (campaignId) {
        const result = await listCampaignLeadsPage(
          campaignId,
          page,
          {
            status: statusParam || undefined,
            search: search || undefined,
            accountId: accountId || undefined,
          },
          limit
        );
        return NextResponse.json({ ok: true, ...result });
      }

      const where = buildLeadWhere({
        status: statusParam || undefined,
        search,
        accountId: accountId || undefined,
      });
      const skip = (page - 1) * limit;
      // leadTableSelect's nested `linkedInAccount` / `campaign` relations become
      // explicit left joins — both FKs are nullable, so a missing row must stay
      // `null` in the JSON exactly as Prisma returned it.
      const [rows, [{ n: total }]] = await Promise.all([
        db
          .select({
            id: leads.id,
            sourceLinkedinIdentifier: leads.sourceLinkedinIdentifier,
            stagedName: leads.name,
            stagedHeadline: leads.headline,
            stagedLocation: leads.location,
            stagedProfilePictureUrl: leads.profilePictureUrl,
            person: people,
            company: companies,
            status: leads.status,
            createdAt: leads.createdAt,
            updatedAt: leads.updatedAt,
            accountUsername: linkedInAccounts.username,
            accountName: linkedInAccounts.name,
            accountProfilePictureUrl: linkedInAccounts.profilePictureUrl,
            campaignId: campaigns.id,
            campaignName: campaigns.name,
          })
          .from(leads)
          .leftJoin(people, eq(leads.personId, people.id))
          .leftJoin(companies, eq(people.companyId, companies.id))
          .leftJoin(linkedInAccounts, eq(leads.linkedinAccountId, linkedInAccounts.id))
          .leftJoin(campaigns, eq(leads.campaignId, campaigns.id))
          .where(where)
          .orderBy(desc(leads.updatedAt))
          .offset(skip)
          .limit(limit),
        db.select({ n: count() }).from(leads).where(where),
      ]);

      return NextResponse.json({
        ok: true,
        leads: rows.map(
          ({
            accountUsername,
            accountName,
            accountProfilePictureUrl,
            campaignId: joinedCampaignId,
            campaignName,
            person,
            company,
            ...l
          }) => ({
            ...l,
            ...(person ? personProfile(person, company) : {
              email: null,
              linkedinUrl: l.sourceLinkedinIdentifier ?? "",
              firstName: null,
              lastName: null,
              name: l.stagedName,
              headline: l.stagedHeadline,
              location: l.stagedLocation,
              profilePictureUrl: l.stagedProfilePictureUrl,
              company: null,
              variables: {},
            }),
            linkedInAccount:
              accountUsername === null
                ? null
                : {
                    username: accountUsername,
                    name: accountName,
                    profilePictureUrl: accountProfilePictureUrl,
                  },
            campaign:
              joinedCampaignId === null ? null : { id: joinedCampaignId, name: campaignName! },
            createdAt: l.createdAt.toISOString(),
            updatedAt: l.updatedAt.toISOString(),
          })
        ),
        pagination: { page, limit, total, pages: Math.ceil(total / limit) },
      });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}

export async function POST() {
  // General LinkedIn search/export data must remain staged. People and Lead
  // rows are created by a campaign-scoped upload or the grid mapping flow.
  return NextResponse.json({ ok: false, error: IMPORT_FAILURE.CAMPAIGN_REQUIRED }, { status: 400 });
}
