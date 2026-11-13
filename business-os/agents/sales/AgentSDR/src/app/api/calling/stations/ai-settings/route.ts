import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { listStationAiSettings } from "@/lib/calls/stationSettings";

/** Each calling number's own AI calls a day and calling hours, with the organization rules they fall back to. */
export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => Response.json(await listStationAiSettings()));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
