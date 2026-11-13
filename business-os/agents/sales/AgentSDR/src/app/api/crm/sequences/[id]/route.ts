import { type NextRequest } from "next/server";
import {
  crmConfigurationErrorResponse,
  readCrmJson,
} from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { deleteSequence, getSequence, updateSequence } from "@/lib/crm/sequences";
import { withOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";

type Context = { params: Promise<{ id: string }> };

export async function GET(request: NextRequest, { params }: Context) {
  try {
    return await withOrgContext(request, async () => {
      const { id } = await params;
      return Response.json({ sequence: await getSequence(id) });
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}

export async function PATCH(request: NextRequest, { params }: Context) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const { id } = await params;
      const sequence = await updateSequence(id, await readCrmJson(request));
      return Response.json({ sequence });
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}

export async function DELETE(request: NextRequest, { params }: Context) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const { id } = await params;
      return Response.json({ deleted: await deleteSequence(id) });
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}
