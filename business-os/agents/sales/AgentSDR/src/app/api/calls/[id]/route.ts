import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import { callApiErrorResponse, getCall } from "@/lib/calls/sessions";

// Proxy-gated GET, like every other GET route under /api/calls — no
// requireCrmMutationContext here (see src/app/api/calls/route.ts's GET).
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const id = (await params).id;
    return await withOrgContext(request, async () => Response.json(await getCall(id)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
