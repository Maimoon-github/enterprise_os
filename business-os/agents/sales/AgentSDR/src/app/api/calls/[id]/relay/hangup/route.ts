import type { NextRequest } from "next/server";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { CallApiError, callApiErrorResponse, getCallInOrganization, isTerminalStatus } from "@/lib/calls/sessions";
import { hangUpRelay } from "@/lib/calls/remoteRep";
import { runInOrganization } from "@/lib/tenancy/scope";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * The rep's Hang up on a call they talk on through a calling station: the
 * station is told to end the WhatsApp call (contract.ts, "a rep talking
 * through a calling station"). A call that is already over answers 204 too.
 * A call that has not connected is also withdrawn, with /cancel.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    await runInOrganization(ctx.organizationId, async () => {
      const row = await getCallInOrganization(id);
      if (!row.remoteRep) throw new CallApiError(409, "This call is not one a rep talks on");
      if (!isTerminalStatus(row.status)) hangUpRelay(id);
    });
    return new Response(null, { status: 204 });
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
