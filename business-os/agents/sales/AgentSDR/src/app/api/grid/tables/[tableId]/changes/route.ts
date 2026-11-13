import { NextRequest, NextResponse } from "next/server";
import { changesSince } from "@/lib/grid/rows";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { isUuid } from "@/lib/grid/validate";

/**
 * GET /api/grid/tables/[tableId]/changes?cursor=<version>
 *
 * The polling endpoint. Returns rows written since `cursor`, the new cursor,
 * and how many jobs are still queued or running — the client polls while
 * activeJobs > 0 and stops when it reaches zero.
 *
 * `cursor` comes from the table GET, so a client never starts at 0 and never
 * refetches the whole table on its first poll.
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ tableId: string }> },
) {
  try {
    return await withOrgContext(req, async () => {
      const { tableId } = await params;
      if (!isUuid(tableId)) return NextResponse.json({ error: "table not found" }, { status: 404 });

      // next dev does not always re-run instrumentation after a hot reload. Start
      // the idempotent, SKIP-LOCKED worker here as a development safety net.
      if (process.env.NODE_ENV !== "production") {
        const { startGridWorker } = await import("@/lib/grid/worker");
        startGridWorker();
      }

      const raw = req.nextUrl.searchParams.get("cursor");
      const cursor = Number(raw ?? 0);
      if (!Number.isFinite(cursor) || cursor < 0) {
        return NextResponse.json({ error: "cursor must be a non-negative number" }, { status: 400 });
      }

      const result = await changesSince(tableId, cursor);
      return NextResponse.json(result);
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
