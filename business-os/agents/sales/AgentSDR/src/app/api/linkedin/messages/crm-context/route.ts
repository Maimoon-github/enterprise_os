import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { loadInboxCrmContext } from "@/lib/linkedin/messages/crmContext.server";

export const dynamic = "force-dynamic";

/** CRM state for the open thread; `context` is null when the thread is not a CRM conversation. */
export async function GET(req: NextRequest) {
  return withLinkedinOrg(req, async () => {
    const connectionId = req.nextUrl.searchParams.get("connectionId");
    if (!connectionId) {
      return NextResponse.json({ error: "connectionId required" }, { status: 400 });
    }

    const context = await loadInboxCrmContext(connectionId);
    return NextResponse.json({ context });
  });
}
