import { type NextRequest } from "next/server";
import { crmConfigurationErrorResponse } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { publishSequence } from "@/lib/crm/sequences";
import { runInOrganization } from "@/lib/tenancy/scope";

type Context = { params: Promise<{ id: string }> };

export async function POST(request: NextRequest, { params }: Context) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const { id } = await params;
      return Response.json(await publishSequence(id));
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}
