import type { NextRequest } from "next/server";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { cancelLink, requestLink } from "@/lib/calls/stations";
import { runInOrganization } from "@/lib/tenancy/scope";

/** Ask a call worker to open this number's WhatsApp Web login, so the operator can link it. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    const body = (await request.json().catch(() => null)) as { fresh?: unknown } | null;
    return await runInOrganization(ctx.organizationId, async () => Response.json({ station: await requestLink(id, body?.fresh === true) }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = (await params).id;
    return await runInOrganization(ctx.organizationId, async () => Response.json({ station: await cancelLink(id) }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
