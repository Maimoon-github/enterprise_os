import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { callApiErrorResponse, finishCall, parseFinishCallRequest, withRecorderScope } from "@/lib/calls/sessions";

/** Extension-only, bearer-token authorized — see the started/ route's comment. Idempotent once terminal. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withRecorderScope(request, (await params).id, async (row) => {
      const body = parseFinishCallRequest(await readCrmJson(request));
      return Response.json({ call: await finishCall(row, body) });
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
