import { type NextRequest } from "next/server";
import {
  crmConfigurationErrorResponse,
  readCrmJson,
} from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { createSequence, listSequences } from "@/lib/crm/sequences";
import { withOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => {
      const sequences = await listSequences({
        includeArchived: request.nextUrl.searchParams.get("includeArchived") === "true",
      });
      return Response.json({ sequences });
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}

export async function POST(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const sequence = await createSequence(await readCrmJson(request));
      return Response.json({ sequence }, { status: 201 });
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}
