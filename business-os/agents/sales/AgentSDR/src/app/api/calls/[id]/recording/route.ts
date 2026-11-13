import type { NextRequest } from "next/server";
import { parseUuid } from "@/lib/crm/categories";
import { callApiErrorResponse, getCallForDownload } from "@/lib/calls/sessions";
import { presignRecordingDownload } from "@/lib/calls/storage";
import { withOrgContext } from "@/lib/auth/context";

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const id = parseUuid((await params).id, "call id");
    return await withOrgContext(request, async () => {
      const row = await getCallForDownload(id);
      const url = await presignRecordingDownload(row.recordingKey!);
      return Response.redirect(url, 302);
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
