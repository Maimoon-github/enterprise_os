import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { withOrgContext } from "@/lib/auth/context";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { createStation, listStations, parseCreateStationRequest } from "@/lib/calls/stations";
import { runInOrganization } from "@/lib/tenancy/scope";

/** Cloud calling numbers (see src/lib/calls/stations.ts). */
export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => Response.json({ stations: await listStations() }));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}

export async function POST(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const body = parseCreateStationRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () =>
      Response.json({ station: await createStation(body) }, { status: 201 }),
    );
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
