import { NextRequest, NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { mailboxes } from "@/lib/outreach/schema";
import { inOrg } from "@/lib/tenancy/scope";
import { withOrgContext, authContextErrorResponse } from "@/lib/auth/context";

// PATCH /api/outreach/mailboxes/[id]/signature — { signatureHtml: string | null }
export async function PATCH(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withOrgContext(req, async () => {
      const { id } = await params;
      let body: { signatureHtml?: string | null };
      try {
        body = await req.json();
      } catch {
        return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
      }
      await db
        .update(mailboxes)
        .set({ signatureHtml: body.signatureHtml?.trim() || null, updatedAt: new Date() })
        .where(and(inOrg(mailboxes), eq(mailboxes.id, id)));
      return NextResponse.json({ ok: true });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
