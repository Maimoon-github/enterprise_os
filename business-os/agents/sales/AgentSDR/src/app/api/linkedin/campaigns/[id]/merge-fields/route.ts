import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, asc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { companies, people } from "@/lib/leads/schema";
import { personProfile, personVariables } from "@/lib/leads/variables";
import { leads } from "@/lib/linkedin/schema";

const DEFAULT_FIELDS = ["firstName", "lastName", "fullName", "title", "company", "companyDomain"];

function labelFor(token: string) {
  return token
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(_req, async () => {
    const { id } = await params;
    const rows = await db
      .select({ leadId: leads.id, person: people, company: companies })
      .from(leads)
      .innerJoin(people, eq(leads.personId, people.id))
      .leftJoin(companies, eq(people.companyId, companies.id))
      .where(and(inOrg(leads), eq(leads.campaignId, id)))
      .orderBy(asc(leads.createdAt))
      .limit(250);

    const tokens = new Set(DEFAULT_FIELDS);
    for (const row of rows) {
      for (const token of Object.keys(personVariables(row.person, row.company))) tokens.add(token);
    }

    return NextResponse.json({
      fields: [...tokens].map((token) => ({ token, label: labelFor(token) })),
      leads: rows.map((row) => {
        const profile = personProfile(row.person, row.company);
        return {
          id: row.leadId,
          name: profile.name,
          linkedinUrl: profile.linkedinUrl,
        };
      }),
    });
  });
}
