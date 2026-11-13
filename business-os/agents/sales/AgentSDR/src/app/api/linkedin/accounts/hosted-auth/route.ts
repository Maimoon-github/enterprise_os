import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { currentOrganizationId, inOrg } from "@/lib/tenancy/scope";
import { linkedInAccounts } from "@/lib/linkedin/schema";
import { createLinkedInHostedAuthLink } from "@/services/unipile.service";
import { hostedAuthCallbackUrls } from "@/lib/linkedin/hostedAuthUrls";
import { isPlatformNotConnectedError, requirePlatformCredentials } from "@/lib/platform/credentials";
import { serializeError } from "@/lib/linkedin/serializeError";

// POST /api/linkedin/accounts/hosted-auth
//   {}                     → link that connects a new LinkedIn account
//   { accountId: "<id>" }  → link that re-authenticates that account in place
//
// Returns a single-use Unipile URL the caller navigates to. Unipile advises
// against iframing the wizard, so this deliberately returns a URL rather than
// anything embeddable.
export async function POST(req: NextRequest) {
  return withLinkedinOrg(req, async () => {
    try {
      const credentials = await requirePlatformCredentials("unipile");
      const body = await req.json().catch(() => ({}));
      const accountId = typeof body?.accountId === "string" ? body.accountId : null;

      let reconnectAccountId: string | null = null;
      if (accountId) {
        const [account] = await db
          .select({ id: linkedInAccounts.id, linkedinId: linkedInAccounts.linkedinId })
          .from(linkedInAccounts)
          .where(and(inOrg(linkedInAccounts), eq(linkedInAccounts.id, accountId)))
          .limit(1);
        if (!account) {
          return NextResponse.json({ ok: false, error: "Account not found" }, { status: 404 });
        }
        // linkedinId is the Unipile account id — what `reconnect_account` expects.
        reconnectAccountId = account.linkedinId;
      }

      const url = await createLinkedInHostedAuthLink({
        name: accountId ?? "agentsdr",
        reconnectAccountId,
        // The browser's own origin, so a dev session returns to localhost
        // instead of production.
        ...hostedAuthCallbackUrls(req.headers.get("origin"), credentials.notifySecret, currentOrganizationId()),
      });

      return NextResponse.json({ ok: true, url });
    } catch (err) {
      if (isPlatformNotConnectedError(err)) {
        return NextResponse.json({ ok: false, error: err.message }, { status: 409 });
      }
      console.error(`[hosted-auth] Failed to create link: ${serializeError(err)}`);
      return NextResponse.json({ ok: false, error: serializeError(err) }, { status: 500 });
    }
  });
}
