import type { NextRequest } from "next/server";
import { withOrgContext } from "@/lib/auth/context";
import type { PersonWhatsappThreadResponse } from "@/lib/whatsapp/contract";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { assertIdParam } from "@/lib/whatsapp/http";
import { getPersonWhatsappThread } from "@/lib/whatsapp/messages";

/** GET /api/whatsapp/people/:personId/thread — the lead's latest chat, for Calling and the CRM record. Proxy-gated. */
export async function GET(request: NextRequest, { params }: { params: Promise<{ personId: string }> }) {
  try {
    const personId = assertIdParam((await params).personId, "Person");
    return await withOrgContext(request, async () =>
      Response.json((await getPersonWhatsappThread(personId)) satisfies PersonWhatsappThreadResponse));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
