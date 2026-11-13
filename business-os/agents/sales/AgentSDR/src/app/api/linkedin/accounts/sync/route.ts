import { NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { syncAllAccounts } from "@/functions/syncAllAccounts";
import { isPlatformNotConnectedError, requirePlatformCredentials } from "@/lib/platform/credentials";
import { serializeError } from "@/lib/linkedin/serializeError";

// POST /api/linkedin/accounts/sync — pulls the Unipile account list into
// LinkedInAccount on demand. Until this existed the only path was the
// cron-driven outreach tick, so a freshly connected account stayed invisible
// until the next run; the hosted-auth return calls this so it shows up at once.
// Upserts, so calling it repeatedly is harmless.
export async function POST(req: Request) {
  return withLinkedinOrg(req, async () => {
    try {
      await requirePlatformCredentials("unipile");
      await syncAllAccounts();
      return NextResponse.json({ ok: true });
    } catch (err) {
      if (isPlatformNotConnectedError(err)) {
        return NextResponse.json({ ok: false, error: err.message }, { status: 409 });
      }
      console.error(`[accounts/sync] ${serializeError(err)}`);
      return NextResponse.json({ ok: false, error: serializeError(err) }, { status: 500 });
    }
  });
}
