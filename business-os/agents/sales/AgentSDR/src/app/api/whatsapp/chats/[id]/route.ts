import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import type { WhatsappThreadResponse } from "@/lib/whatsapp/contract";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { assertIdParam } from "@/lib/whatsapp/http";
import { getWhatsappThread } from "@/lib/whatsapp/messages";

/** GET /api/whatsapp/chats/:id — the chat and its messages, oldest first. Proxy-gated. */
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const id = assertIdParam((await params).id, "WhatsApp chat");
    return await withOrgContext(request, async () =>
      Response.json((await getWhatsappThread(id)) satisfies WhatsappThreadResponse));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
