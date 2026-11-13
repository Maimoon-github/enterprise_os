import { NextRequest, NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { inOrg } from "@/lib/tenancy/scope";
import { webhookEvents } from "@/lib/linkedin/schema";

export const dynamic = "force-dynamic";

// Returns a stored webhook body to the UI, so it stays behind auth (never
// public in proxy.ts) and reads only the caller's organization's events.
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    return await withOrgContext(req, () => readEvent(id));
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

async function readEvent(id: string): Promise<NextResponse> {
  const [ev] = await db
    .select({
      rawBody: webhookEvents.rawBody,
      processingLog: webhookEvents.processingLog,
    })
    .from(webhookEvents)
    .where(and(inOrg(webhookEvents), eq(webhookEvents.id, id)))
    .limit(1);

  if (!ev) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  return NextResponse.json({
    rawBody: ev.rawBody,
    processingLog: ev.processingLog as { level: string; message: string; time: string }[] | null,
  });
}
