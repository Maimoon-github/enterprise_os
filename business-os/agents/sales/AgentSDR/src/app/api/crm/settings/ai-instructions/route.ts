import { type NextRequest } from "next/server";
import { getCrmAiInstructions, updateCrmAiInstructions } from "@/lib/crm/aiSettings";
import { crmConfigurationErrorResponse, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { withOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => {
      return Response.json(
        await getCrmAiInstructions(request.nextUrl.searchParams.get("pipelineId") ?? undefined),
      );
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}

export async function PUT(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      return Response.json(await updateCrmAiInstructions(await readCrmJson(request)));
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}
