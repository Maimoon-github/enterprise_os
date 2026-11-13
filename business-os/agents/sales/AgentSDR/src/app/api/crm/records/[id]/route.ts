import type { NextRequest } from "next/server";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { getCrmRecordWorkspace } from "@/lib/crm/queries";
import { withOrgContext } from "@/lib/auth/context";

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    return await withOrgContext(request, async () => {
      return Response.json(await getCrmRecordWorkspace((await params).id));
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
