import type { NextRequest } from "next/server";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { runInOrganization } from "@/lib/tenancy/scope";
import { syncWhatsappAccounts } from "@/lib/whatsapp/accounts";
import type { ListWhatsappAccountsResponse } from "@/lib/whatsapp/contract";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";

/** POST /api/whatsapp/accounts/sync — re-reads the linked numbers from Unipile. */
export async function POST(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () =>
      Response.json({ accounts: await syncWhatsappAccounts() } satisfies ListWhatsappAccountsResponse));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
