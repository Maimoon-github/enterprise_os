import type { NextRequest } from "next/server";
import { callApiErrorResponse, CallApiError } from "@/lib/calls/sessions";
import { PHOTO_FILE_PATTERN, photoKey, presignPhotoDownload } from "@/lib/calls/storage";
import { withOrgContext } from "@/lib/auth/context";
import { assertPersonInOrg } from "@/lib/calls/campaigns";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * An uploaded contact photo → a short-lived R2 link. Behind the app's auth
 * like every /api/calling route (proxy.ts); the stored path never exposes a
 * bucket URL. Browsers may reuse the redirect for a while, well inside the
 * link's hour.
 */
export async function GET(request: NextRequest, { params }: { params: Promise<{ personId: string; file: string }> }) {
  try {
    const { personId, file } = await params;
    if (!UUID_PATTERN.test(personId) || !PHOTO_FILE_PATTERN.test(file)) throw new CallApiError(404, "Photo not found");
    const url = await withOrgContext(request, async () => {
      await assertPersonInOrg(personId);
      return presignPhotoDownload(photoKey(personId.toLowerCase(), file));
    });
    return new Response(null, { status: 302, headers: { Location: url, "Cache-Control": "private, max-age=1800" } });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
