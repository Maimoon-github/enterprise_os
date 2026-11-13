import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, asc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { messages } from "@/lib/linkedin/schema";
import { isDemoMode } from "@/lib/demo/mode";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return withLinkedinOrg(req, async () => {
    const connectionId = req.nextUrl.searchParams.get("connectionId");
    if (!connectionId) {
      return NextResponse.json({ error: "connectionId required" }, { status: 400 });
    }

    const thread = await db
      .select({
        id: messages.id,
        type: messages.type,
        text: messages.text,
        seen: messages.seen,
        createdAt: messages.createdAt,
      })
      .from(messages)
      .where(and(inOrg(messages), eq(messages.connectionId, connectionId)))
      .orderBy(asc(messages.createdAt));

    // The demo is read-only: opening a thread must not mark it read for every later visitor.
    if (!isDemoMode()) await db
      .update(messages)
      .set({ seen: true })
      .where(and(inOrg(messages), eq(messages.connectionId, connectionId), eq(messages.seen, false)));

    return NextResponse.json({
      messages: thread.map((m) => ({ ...m, createdAt: m.createdAt.toISOString() })),
    });
  });
}
