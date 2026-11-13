import { NextRequest, NextResponse } from "next/server";
import { renewMailboxWatches } from "@/lib/outreach/mailboxWatch";
import { cronOrganizationFilter } from "@/lib/scheduler/endpoint";

// POST /api/outreach/mailboxes/watch — (re)registers Gmail Pub/Sub push
// notifications for every connected mailbox. Watches expire after ~7 days;
// the in-process scheduler renews them in each organization's daily
// rollover. This endpoint remains for a manual run or an external cron:
// while the scheduler runs it skips organizations that already rolled over
// today (`?force=1` renews them anyway). Same OUTREACH_TICK_SECRET
// protection as /api/outreach/tick (not cookie-authenticated).
export async function POST(req: NextRequest) {
  const expected = process.env.OUTREACH_TICK_SECRET;
  const provided = req.nextUrl.searchParams.get("secret") ?? req.headers.get("x-tick-secret");
  if (!expected || provided !== expected) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const { organizationIds, alreadyRolledOver } = await cronOrganizationFilter(req);
  const result = await renewMailboxWatches({ organizationIds });
  return NextResponse.json(alreadyRolledOver ? { ...result, alreadyRolledOver } : result);
}
