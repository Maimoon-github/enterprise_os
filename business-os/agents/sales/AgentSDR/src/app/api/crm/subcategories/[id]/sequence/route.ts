import { type NextRequest } from "next/server";
import {
  crmConfigurationErrorResponse,
  readCrmJson,
} from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { assignSubcategorySequence } from "@/lib/crm/sequences";
import { runInOrganization } from "@/lib/tenancy/scope";

type Context = { params: Promise<{ id: string }> };

export async function PUT(request: NextRequest, { params }: Context) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const { id } = await params;
      const assignment = await assignSubcategorySequence(id, await readCrmJson(request));
      return Response.json({ assignment });
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}
