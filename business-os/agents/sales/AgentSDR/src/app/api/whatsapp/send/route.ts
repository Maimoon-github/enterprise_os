import type { NextRequest } from "next/server";
import { readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import type { SendWhatsappResponse } from "@/lib/whatsapp/contract";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { parseSendWhatsappRequest } from "@/lib/whatsapp/http";
import { sendWhatsapp } from "@/lib/whatsapp/send";
import { runInOrganization } from "@/lib/tenancy/scope";

/**
 * POST /api/whatsapp/send — sends through Unipile. 409 while warming up /
 * over the new-chat cap / Do Not Contact, 429 (Retry-After, retryAfterSeconds)
 * when sent too soon after the account's last send. See contract.ts.
 */
export async function POST(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const body = parseSendWhatsappRequest(await readCrmJson(request));
    return await runInOrganization(ctx.organizationId, async () =>
      Response.json((await sendWhatsapp(body)) satisfies SendWhatsappResponse));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
