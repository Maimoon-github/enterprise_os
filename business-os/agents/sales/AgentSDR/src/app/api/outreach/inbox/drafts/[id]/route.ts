import { NextRequest, NextResponse } from "next/server";
import { and, eq, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { inboxContacts, inboxDrafts } from "@/lib/inbox/schema";
import { inOrg, runInOrganization } from "@/lib/tenancy/scope";
import { requireOrgContext, authContextErrorResponse } from "@/lib/auth/context";

// DELETE /api/outreach/inbox/drafts/[id] — reject/discard a pending AI draft.
export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireOrgContext(_req);
    return await runInOrganization(ctx.organizationId, async () => {
      const { id } = await params;
      await db.delete(inboxDrafts).where(and(
        eq(inboxDrafts.id, id),
        inArray(inboxDrafts.contactId, db.select({ id: inboxContacts.id }).from(inboxContacts).where(inOrg(inboxContacts))),
      ));
      return NextResponse.json({ ok: true });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
