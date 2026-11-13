import { callApiErrorResponse } from "@/lib/calls/sessions";
import { authorizeWorker, commitProfile, parseProfileCommitRequest } from "@/lib/calls/stations";

/** The uploaded profile becomes the number's current one (409 if a newer save landed first). */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    authorizeWorker(request);
    const body = parseProfileCommitRequest(await request.json().catch(() => null));
    return Response.json(await commitProfile((await params).id, body));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
