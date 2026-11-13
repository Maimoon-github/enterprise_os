import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { setDefaultWhatsappAccount, setWhatsappNewChatsPerDay } from "@/lib/whatsapp/accounts";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { assertIdParam, parseAccountUpdateRequest } from "@/lib/whatsapp/http";
import { runInOrganization } from "@/lib/tenancy/scope";

/**
 * PATCH /api/whatsapp/accounts/:id
 *   { isDefault: true } — makes it the default sending number.
 *   { newChatsPerDay: n | null } — its own new-chats-a-day limit, or back to the organization's.
 */
export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = assertIdParam((await params).id, "WhatsApp account");
    const update = parseAccountUpdateRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () =>
      Response.json("isDefault" in update ? await setDefaultWhatsappAccount(id) : await setWhatsappNewChatsPerDay(id, update.newChatsPerDay)),
    );
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
