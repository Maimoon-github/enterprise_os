import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { callApiErrorResponse, issueUploadUrl, parseUploadUrlRequest, withRecorderScope } from "@/lib/calls/sessions";

/** Extension-only, bearer-token authorized — see the started/ route's comment. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withRecorderScope(request, (await params).id, async (row) => {
      const body = parseUploadUrlRequest(await readCrmJson(request));
      return Response.json(await issueUploadUrl(row, body));
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
