import { NextRequest, NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { mailboxes } from "@/lib/outreach/schema";
import { syncMailboxInbox } from "@/lib/outreach/gmailSync";
import { runInOrganization } from "@/lib/tenancy/scope";

// POST /api/outreach/webhooks/gmail-watch — Google Cloud Pub/Sub push
// endpoint. Payload shape: { message: { data: base64(JSON({emailAddress,
// historyId})), messageId, publishTime }, subscription }. No shared-secret
// query param (Pub/Sub push doesn't support that cleanly) — instead we only
// trust addresses that are actually one of our connected mailboxes. There is
// no session: the mailbox (email_address is globally unique) names the
// organization, and the sync runs in that organization's scope.
export async function POST(req: NextRequest) {
  let body: { message?: { data?: string } };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const data = body.message?.data;
  if (!data) return NextResponse.json({ ok: true }); // malformed/empty push — ack anyway so Pub/Sub doesn't retry forever

  let decoded: { emailAddress?: string; historyId?: string | number };
  try {
    decoded = JSON.parse(Buffer.from(data, "base64").toString("utf-8"));
  } catch {
    return NextResponse.json({ ok: true });
  }

  const emailAddress = decoded.emailAddress?.trim().toLowerCase();
  if (!emailAddress) return NextResponse.json({ ok: true });

  const [mailbox] = await db.select().from(mailboxes).where(eq(mailboxes.emailAddress, emailAddress)).limit(1);
  if (!mailbox) return NextResponse.json({ ok: true }); // not one of ours — ignore

  try {
    const result = await runInOrganization(mailbox.organizationId, () => syncMailboxInbox(mailbox.id));
    return NextResponse.json({ ok: true, ...result });
  } catch (err) {
    console.error("[outreach/webhooks/gmail-watch] sync failed:", err);
    // Still 200 — Pub/Sub retries on non-2xx, and a stuck mailbox would
    // otherwise retry the same push indefinitely.
    return NextResponse.json({ ok: false });
  }
}
