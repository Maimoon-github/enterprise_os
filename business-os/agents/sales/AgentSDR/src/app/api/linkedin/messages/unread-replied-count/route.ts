import { NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { countUnreadFromRepliedLeads } from "@/lib/linkedin/messages/connectionList.server";

export async function GET(req: Request) {
  return withLinkedinOrg(req, async () => {
    try {
      const count = await countUnreadFromRepliedLeads();
      return NextResponse.json({ ok: true, count });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
