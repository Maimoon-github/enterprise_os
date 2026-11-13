import type { NextRequest } from "next/server";
import { callApiErrorResponse, recorderCallStatus, withRecorderScope } from "@/lib/calls/sessions";

/**
 * The call card on web.whatsapp.com polls this after an upload, to show the
 * transcript arriving. Bearer-token authorized like the rest of this prefix
 * (see the started/ route's comment); the token outlives the call's end.
 */
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withRecorderScope(request, (await params).id, async (row) => Response.json(recorderCallStatus(row)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
