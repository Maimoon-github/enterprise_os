import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import { parseUuid } from "@/lib/crm/categories";
import { CallApiError, callApiErrorResponse, getCallInOrganization } from "@/lib/calls/sessions";
import { headRecording, heardAudioKeyFor, presignRecordingDownload } from "@/lib/calls/storage";

/** What the AI agent heard on this call (test option, see …/call-recorder/calls/[id]/heard-audio). */
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const id = parseUuid((await params).id, "call id");
    return await withOrgContext(request, async () => {
      const row = await getCallInOrganization(id);
      const key = heardAudioKeyFor(row.id, row.createdAt);
      if (!(await headRecording(key))) throw new CallApiError(404, "No heard audio was saved for this call");
      return Response.redirect(await presignRecordingDownload(key), 302);
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
