import { NextRequest, NextResponse } from "next/server";
import { verifyUnsubscribeToken } from "@/lib/outreach/unsubscribeToken";
import { suppressEmailOutreach, suppressEmailOutreachEverywhere } from "@/lib/outreach/suppression";
import { runInOrganization } from "@/lib/tenancy/scope";

// POST /api/outreach/unsubscribe — { token } — public, no auth (see proxy.ts).
// Token is a stateless signed email (see lib/outreach/unsubscribeToken.ts),
// so this endpoint can only ever suppress the one address it was issued for.
// A v2 token carries the organization that mailed it and the scope is opened
// from that; a legacy token names none, so the address is suppressed in every
// organization whose outreach leads contain it.
export async function POST(req: NextRequest) {
  // Two callers with different shapes:
  //  - the /unsubscribe page posts JSON { token }
  //  - RFC 8058 one-click (Gmail/Outlook's native Unsubscribe button) posts
  //    "List-Unsubscribe=One-Click" as form data with the token in the query
  //    string, so fall back to ?token= when the body has none.
  let token = new URL(req.url).searchParams.get("token") ?? undefined;
  if (!token) {
    try {
      const body = (await req.json()) as { token?: string };
      token = body.token;
    } catch {
      token = undefined;
    }
  }
  if (!token) {
    return NextResponse.json({ error: "token is required" }, { status: 400 });
  }

  const result = verifyUnsubscribeToken(token);
  if (!result.ok) {
    return NextResponse.json({ error: "invalid or expired unsubscribe link" }, { status: 400 });
  }

  if (result.organizationId) {
    await runInOrganization(result.organizationId, () =>
      suppressEmailOutreach(result.email, "unsubscribed", "One-click unsubscribe link"),
    );
  } else {
    await suppressEmailOutreachEverywhere(result.email, "unsubscribed", "One-click unsubscribe link");
  }

  return NextResponse.json({ ok: true, email: result.email });
}
