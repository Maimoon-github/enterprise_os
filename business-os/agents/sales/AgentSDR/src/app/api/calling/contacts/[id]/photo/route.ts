import type { NextRequest } from "next/server";
import { CrmConfigurationValidationError } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse, uploadContactPhoto } from "@/lib/calls/campaigns";
import { runInOrganization } from "@/lib/tenancy/scope";

/** Multipart `file`: an image that becomes the person's photo. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const contactId = (await params).id;
    const form = await request.formData().catch(() => null);
    const file = form?.get("file");
    if (!(file instanceof File)) throw new CrmConfigurationValidationError("file is required");
    return await runInOrganization(ctx.organizationId, async () => Response.json(await uploadContactPhoto(contactId, file)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
