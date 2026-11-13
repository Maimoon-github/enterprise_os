import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { parseUuid } from "@/lib/crm/categories";
import { loadInboxEmailCrmContext } from "@/lib/inbox/crmContext.server";

export const dynamic = "force-dynamic";

// GET /api/outreach/inbox/leads/[id]/crm-context
/** CRM state for the open thread; `context` is null when the contact is not a CRM email conversation. */
export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withOrgContext(_req, async () => {
      const contactId = parseUuid((await params).id, "contact id");
      const context = await loadInboxEmailCrmContext(contactId);
      return NextResponse.json({ context });
    });
  } catch (error) {
    return authContextErrorResponse(error) ?? crmOperationErrorResponse(error);
  }
}
