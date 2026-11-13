import { type NextRequest } from "next/server";
import {
  crmConfigurationErrorResponse,
  listCategoryConfiguration,
} from "@/lib/crm/categories";
import { withOrgContext } from "@/lib/auth/context";

export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => {
      const configuration = await listCategoryConfiguration(
        request.nextUrl.searchParams.get("pipelineId") ?? undefined,
      );
      return Response.json(configuration);
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}
