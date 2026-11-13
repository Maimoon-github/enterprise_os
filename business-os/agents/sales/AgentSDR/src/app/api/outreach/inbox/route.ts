import { NextRequest, NextResponse } from "next/server";
import { getMailsBySection, getScheduledEmails } from "@/lib/inbox/queries";
import type { InboxSection } from "@/lib/inbox/queries";
import { withOrgContext, authContextErrorResponse } from "@/lib/auth/context";

const VALID_SECTIONS: InboxSection[] = ["inbox", "sent", "replied", "important", "outOfOffice", "pendingApproval"];

// GET /api/outreach/inbox?section=inbox&q=&page=&pageSize=&leadIds=&campaignIds=&accounts=&statusKeys=&statusGroups=&startDate=&endDate=
export async function GET(req: NextRequest) {
  try {
    return await withOrgContext(req, async () => {
      const sp = req.nextUrl.searchParams;
      const sectionParam = sp.get("section") ?? "inbox";

      if (sectionParam === "scheduled") {
        const result = await getScheduledEmails({
          q: sp.get("q") ?? undefined,
          campaignIds: sp.get("campaignIds")?.split(",").filter(Boolean),
          page: sp.get("page") ? Number(sp.get("page")) : undefined,
          pageSize: sp.get("pageSize") ? Number(sp.get("pageSize")) : undefined,
        });
        return NextResponse.json(result);
      }

      if (!VALID_SECTIONS.includes(sectionParam as InboxSection)) {
        return NextResponse.json({ error: `invalid section: ${sectionParam}` }, { status: 400 });
      }

      const result = await getMailsBySection({
        section: sectionParam as InboxSection,
        q: sp.get("q") ?? undefined,
        leadIds: sp.get("leadIds")?.split(",").filter(Boolean),
        campaignIds: sp.get("campaignIds")?.split(",").filter(Boolean),
        accounts: sp.get("accounts")?.split(",").filter(Boolean),
        statusKeys: sp.get("statusKeys")?.split(",").filter(Boolean),
        statusGroups: sp.get("statusGroups")?.split(",").filter(Boolean),
        startDate: sp.get("startDate") ? new Date(sp.get("startDate")!) : undefined,
        endDate: sp.get("endDate") ? new Date(sp.get("endDate")!) : undefined,
        page: sp.get("page") ? Number(sp.get("page")) : undefined,
        pageSize: sp.get("pageSize") ? Number(sp.get("pageSize")) : undefined,
      });
      return NextResponse.json(result);
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
