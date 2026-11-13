import type { NextRequest } from "next/server";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { assertIdParam } from "@/lib/whatsapp/http";
import { markWhatsappChatRead } from "@/lib/whatsapp/messages";
import { runInOrganization } from "@/lib/tenancy/scope";

/** POST /api/whatsapp/chats/:id/read — clears the chat's unread count in AgentSDR. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const id = assertIdParam((await params).id, "WhatsApp chat");
    return await runInOrganization(ctx.organizationId, async () => Response.json(await markWhatsappChatRead(id)));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
