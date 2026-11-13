import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import { getCrmOverview } from "@/lib/crm/queries";
import { crmOperationErrorResponse } from "@/lib/crm/api";

export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => Response.json(await getCrmOverview()));
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
