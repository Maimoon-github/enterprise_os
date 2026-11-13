import type { NextRequest } from "next/server";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { listCrmIdentityExceptions } from "@/lib/crm/identity";
import { withOrgContext } from "@/lib/auth/context";

export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => {
      const raw = request.nextUrl.searchParams.get("status") ?? "open";
      if (raw !== "open" && raw !== "resolved" && raw !== "ignored") throw new Error("Invalid identity exception status");
      return Response.json({ exceptions: await listCrmIdentityExceptions(raw) });
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
