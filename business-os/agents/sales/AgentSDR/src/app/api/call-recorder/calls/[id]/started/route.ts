import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { callApiErrorResponse, markCallStarted, parseCallStartedRequest, withRecorderScope } from "@/lib/calls/sessions";

/**
 * Called by the recorder extension's service worker, not the app — it
 * carries the per-call bearer token, never the site cookie, so it does not
 * go through requireCrmMutationContext. withRecorderScope is the auth check, and
 * it runs the request as the organization the call belongs to.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withRecorderScope(request, (await params).id, async (row) => {
      const body = parseCallStartedRequest(await readCrmJson(request));
      const call = await markCallStarted(row, new Date(body.startedAt));
      return Response.json({ call });
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
