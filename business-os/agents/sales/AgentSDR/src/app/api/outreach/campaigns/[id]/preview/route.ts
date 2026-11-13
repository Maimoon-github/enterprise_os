import { NextRequest, NextResponse } from "next/server";
import { and, asc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { companies, people } from "@/lib/leads/schema";
import { personVariables } from "@/lib/leads/variables";
import { outreachLeads, mailboxes } from "@/lib/outreach/schema";
import { renderEmail } from "@/lib/outreach/render";
import { inOrg } from "@/lib/tenancy/scope";
import { leadsInOrg } from "@/lib/outreach/orgScope";
import { withOrgContext, authContextErrorResponse } from "@/lib/auth/context";

/**
 * POST /api/outreach/campaigns/[id]/preview
 *
 * Renders a sequence step exactly as the scheduler would, for one lead and one
 * mailbox. Renders through the shared pipeline in render.ts — the same code the
 * real send uses — so a preview can't drift from what actually goes out.
 *
 * Spin-text resolves randomly per call, so re-posting re-rolls the variants.
 */
export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withOrgContext(req, async () => {
      const { id } = await params;
      const body = await req.json().catch(() => null);
      const step = body?.step;
      if (!step || typeof step.subject !== "string" || typeof step.body !== "string") {
        return NextResponse.json({ error: "step {subject, body} is required" }, { status: 400 });
      }

      const row = body?.leadId
        ? (await db
            .select({ lead: outreachLeads, person: people, company: companies })
            .from(outreachLeads)
            .innerJoin(people, eq(outreachLeads.personId, people.id))
            .leftJoin(companies, eq(people.companyId, companies.id))
            .where(and(leadsInOrg(), inOrg(people), eq(outreachLeads.campaignId, id), eq(outreachLeads.id, body.leadId)))
            .limit(1))[0]
        : (await db
            .select({ lead: outreachLeads, person: people, company: companies })
            .from(outreachLeads)
            .innerJoin(people, eq(outreachLeads.personId, people.id))
            .leftJoin(companies, eq(people.companyId, companies.id))
            .where(and(leadsInOrg(), inOrg(people), eq(outreachLeads.campaignId, id)))
            .orderBy(asc(outreachLeads.createdAt))
            .limit(1))[0];

      if (!row?.person.email) {
        return NextResponse.json({ error: "This campaign has no leads to preview with. Import leads first." }, { status: 404 });
      }

      const mailbox = body?.mailboxId
        ? (await db.select().from(mailboxes).where(and(inOrg(mailboxes), eq(mailboxes.id, body.mailboxId))).limit(1))[0]
        : (await db.select().from(mailboxes).where(inOrg(mailboxes)).orderBy(asc(mailboxes.createdAt)).limit(1))[0];

      const variables = personVariables(row.person, row.company);
      const rendered = renderEmail(step, { email: row.person.email, variables }, mailbox?.signatureHtml ?? null);

      // Report which {{tokens}} the template used but this lead can't fill, so an
      // empty subject line is caught here rather than after the send.
      const used = new Set<string>();
      for (const m of `${step.subject} ${step.body}`.matchAll(/\{\{\s*([^{}\r\n]+?)\s*\}\}/g)) used.add(m[1].trim());
      const available = new Map(Object.entries(variables).map(([key, value]) => [key.toLowerCase(), value]));
      const unresolved = [...used].filter((t) => t.toLowerCase() !== "signature" && !available.has(t.toLowerCase()));

      return NextResponse.json({
        subject: rendered.subject,
        body: rendered.body,
        html: rendered.html,
        unresolved,
        lead: { id: row.lead.id, email: row.person.email, variables },
        mailbox: mailbox
          ? { id: mailbox.id, emailAddress: mailbox.emailAddress, displayName: mailbox.displayName, hasSignature: Boolean(mailbox.signatureHtml) }
          : null,
      });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
