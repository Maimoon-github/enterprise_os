import { callApiErrorResponse } from "@/lib/calls/sessions";
import { authorizeWorker, releaseCall } from "@/lib/calls/stations";

/** The worker could not run a claimed call; it is failed with the worker's reason. Idempotent. */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    authorizeWorker(request);
    const body = (await request.json().catch(() => null)) as { error?: unknown } | null;
    await releaseCall((await params).id, typeof body?.error === "string" ? body.error : "");
    return Response.json({ ok: true });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
