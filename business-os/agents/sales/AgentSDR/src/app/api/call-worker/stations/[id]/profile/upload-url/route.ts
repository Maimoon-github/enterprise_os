import { callApiErrorResponse } from "@/lib/calls/sessions";
import { authorizeWorker, profileUploadUrl } from "@/lib/calls/stations";

/** Where the worker PUTs a number's packed browser profile (tar.gz) after a job. */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    authorizeWorker(request);
    const body = (await request.json().catch(() => null)) as { bytes?: unknown } | null;
    return Response.json(await profileUploadUrl((await params).id, body?.bytes));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
