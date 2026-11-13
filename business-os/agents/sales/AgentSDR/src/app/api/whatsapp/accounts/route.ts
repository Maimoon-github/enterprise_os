import { withOrgContext } from "@/lib/auth/context";
import { listWhatsappAccounts } from "@/lib/whatsapp/accounts";
import type { ListWhatsappAccountsResponse } from "@/lib/whatsapp/contract";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";

/** GET /api/whatsapp/accounts — the linked numbers as last synced. Proxy-gated. */
export async function GET(request: Request) {
  try {
    return await withOrgContext(request, async () =>
      Response.json({ accounts: await listWhatsappAccounts() } satisfies ListWhatsappAccountsResponse));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
