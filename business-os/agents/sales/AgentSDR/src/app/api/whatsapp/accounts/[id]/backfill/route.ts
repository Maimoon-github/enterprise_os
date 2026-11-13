import type { NextRequest } from "next/server";
import { requireCrmMutationContext } from "@/lib/crm/http";
import type { BackfillWhatsappAccountResponse } from "@/lib/whatsapp/contract";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { assertIdParam } from "@/lib/whatsapp/http";
import { backfillWhatsappAccount } from "@/lib/whatsapp/messages";
import { runInOrganization } from "@/lib/tenancy/scope";

/**
 * POST /api/whatsapp/accounts/:id/backfill — imports the number's recent
 * chats and messages from Unipile. History only: nothing reaches the CRM.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = assertIdParam((await params).id, "WhatsApp account");
    return await runInOrganization(ctx.organizationId, async () =>
      Response.json((await backfillWhatsappAccount(id)) satisfies BackfillWhatsappAccountResponse));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
