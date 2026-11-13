import { type NextRequest } from "next/server";
import {
  createSubcategory,
  crmConfigurationErrorResponse,
  listSubcategories,
  readCrmJson,
} from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { withOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => {
      const result = await listSubcategories({
        pipelineId: request.nextUrl.searchParams.get("pipelineId") ?? undefined,
        includeArchived: request.nextUrl.searchParams.get("includeArchived") === "true",
      });
      return Response.json(result);
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}

export async function POST(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const subcategory = await createSubcategory(await readCrmJson(request));
      return Response.json({ subcategory }, { status: 201 });
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}
