import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import {
  parseConnectionListFilters,
  parseConnectionListPage,
} from "@/lib/linkedin/messages/connectionList";
import { listConnectionsPage } from "@/lib/linkedin/messages/connectionList.server";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return withLinkedinOrg(req, async () => {
    const { searchParams } = req.nextUrl;
    const page = parseConnectionListPage(searchParams);
    const filters = parseConnectionListFilters(searchParams);
    const result = await listConnectionsPage(page, filters);

    return NextResponse.json({ ok: true, ...result });
  });
}
