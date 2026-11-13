import { callApiErrorResponse } from "@/lib/calls/sessions";
import { authorizeWorker, workerCallStatus } from "@/lib/calls/stations";

/** Whether a cloud call is over (finished by the extension), so the worker can close its browser. */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    authorizeWorker(request);
    return Response.json(await workerCallStatus((await params).id));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
