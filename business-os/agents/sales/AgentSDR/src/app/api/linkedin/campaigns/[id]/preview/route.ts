import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, asc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { companies, people } from "@/lib/leads/schema";
import { personProfile, personVariables } from "@/lib/leads/variables";
import { LINKEDIN_SEQUENCE_FIELDS, type LinkedinSequenceField } from "@/lib/linkedin/campaignSequence";
import { MAX_INVITATION_MESSAGE_LENGTH } from "@/lib/linkedin/invitationMessage";
import { leads } from "@/lib/linkedin/schema";
import { fillTemplate } from "@/lib/outreach/render";

const TOKEN_PATTERN = /\{\{\s*([^{}\r\n]+?)\s*\}\}/g;

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(req, async () => {
    const { id } = await params;
    const body = await req.json().catch(() => null);
    const template = body?.template;
    const field = body?.field as LinkedinSequenceField | undefined;
    if (typeof template !== "string" || !field || !LINKEDIN_SEQUENCE_FIELDS.includes(field)) {
      return NextResponse.json({ error: "A valid sequence field and template are required" }, { status: 400 });
    }

    const where = body?.leadId
      ? and(inOrg(leads), eq(leads.campaignId, id), eq(leads.id, body.leadId))
      : and(inOrg(leads), eq(leads.campaignId, id));
    const [row] = await db
      .select({ lead: leads, person: people, company: companies })
      .from(leads)
      .innerJoin(people, eq(leads.personId, people.id))
      .leftJoin(companies, eq(people.companyId, companies.id))
      .where(where)
      .orderBy(asc(leads.createdAt))
      .limit(1);

    if (!row) {
      return NextResponse.json({ error: "Add at least one lead to preview this sequence" }, { status: 404 });
    }

    const variables = personVariables(row.person, row.company);
    const used = new Set<string>();
    for (const match of template.matchAll(TOKEN_PATTERN)) used.add(match[1]!.trim());
    const available = new Set(Object.keys(variables).map((key) => key.toLowerCase()));
    const unresolved = [...used].filter((token) => !available.has(token.toLowerCase()));
    const rendered = fillTemplate(template, variables);
    const profile = personProfile(row.person, row.company);

    return NextResponse.json({
      rendered,
      unresolved,
      exceedsInvitationLimit: field === "invitationMessage" && rendered.length > MAX_INVITATION_MESSAGE_LENGTH,
      lead: { id: row.lead.id, name: profile.name, linkedinUrl: profile.linkedinUrl },
    });
  });
}
