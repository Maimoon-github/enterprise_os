import type { NextRequest } from "next/server";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse, getCall, requireRecordedCall } from "@/lib/calls/sessions";
import { transcribeCall } from "@/lib/calls/transcription";
import { runInOrganization } from "@/lib/tenancy/scope";

/**
 * Re-runs transcription for a call that already has a recording. The finish
 * route already starts this on its own (fire-and-forget); this is the
 * rep-triggered retry, so it claims the row (see transcription.ts) and waits
 * for the result before answering.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    return await runInOrganization(ctx.organizationId, async () => {
      await requireRecordedCall(id);
      await transcribeCall(id, { claim: true });
      return Response.json(await getCall(id));
    });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
