import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import type { ListWhatsappChatsResponse } from "@/lib/whatsapp/contract";
import { WhatsappApiError, whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { optionalUuidQuery } from "@/lib/whatsapp/http";
import { listWhatsappChats } from "@/lib/whatsapp/messages";

/** GET /api/whatsapp/chats?accountId=&search=&unread=true&cursor= — newest activity first. Proxy-gated. */
export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams;
    const unread = params.get("unread");
    if (unread !== null && unread !== "true" && unread !== "false") throw new WhatsappApiError(400, "unread must be true or false");
    const search = params.get("search");
    if (search && search.length > 200) throw new WhatsappApiError(400, "search must be at most 200 characters");
    const accountId = optionalUuidQuery(params.get("accountId"), "accountId");
    const response: ListWhatsappChatsResponse = await withOrgContext(request, () => listWhatsappChats({
      accountId,
      search,
      unread: unread === "true",
      cursor: params.get("cursor") || null,
    }));
    return Response.json(response);
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
