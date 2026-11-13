import { NextRequest, NextResponse } from "next/server";
import { requirePlatformOperator } from "@/lib/auth/context";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { asc, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { jobLogs } from "@/lib/linkedin/schema";

export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  // Job logs span every organization's accounts: operator only.
  return withLinkedinOrg(_req, async (ctx) => {
    await requirePlatformOperator(ctx);
    const { id } = await params;

    const logs = await db
      .select({
        id: jobLogs.id,
        level: jobLogs.level,
        message: jobLogs.message,
        createdAt: jobLogs.createdAt,
      })
      .from(jobLogs)
      .where(eq(jobLogs.jobRunId, id))
      .orderBy(asc(jobLogs.createdAt));

    return NextResponse.json({
      logs: logs.map((l) => ({ ...l, createdAt: l.createdAt.toISOString() })),
    });
  });
}
