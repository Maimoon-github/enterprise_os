import { type NextRequest } from "next/server";
import {
  crmConfigurationErrorResponse,
  readCrmJson,
} from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import {
  getKnowledgeDocument,
  updateKnowledgeDocument,
} from "@/lib/crm/knowledge-service";
import { withOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";

type Context = { params: Promise<{ id: string }> };

export async function GET(request: NextRequest, { params }: Context) {
  try {
    return await withOrgContext(request, async () => {
      const { id } = await params;
      return Response.json({ document: await getKnowledgeDocument(id) });
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
      const document = await updateKnowledgeDocument(id, await readCrmJson(request));
      return Response.json({ document });
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}
