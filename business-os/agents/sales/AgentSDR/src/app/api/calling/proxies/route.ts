import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { withOrgContext } from "@/lib/auth/context";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { createProxy, listProxies, parseCreateProxyRequest } from "@/lib/calls/proxies";
import { runInOrganization } from "@/lib/tenancy/scope";

/** The IPs calling numbers go out from (see src/lib/calls/proxies.ts). */
export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => Response.json({ proxies: await listProxies() }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

export async function POST(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const body = parseCreateProxyRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () =>
      Response.json({ proxy: await createProxy(body) }, { status: 201 }),
    );
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
