import { type NextRequest } from "next/server";
import {
  crmConfigurationErrorResponse,
  readCrmJson,
} from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import {
  createKnowledgeDocument,
  listKnowledgeDocuments,
} from "@/lib/crm/knowledge-service";
import { withOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => {
      const documents = await listKnowledgeDocuments({
        kind: request.nextUrl.searchParams.get("kind") ?? undefined,
        includeArchived: request.nextUrl.searchParams.get("includeArchived") === "true",
      });
      return Response.json({ documents });
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}

export async function POST(request: NextRequest) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const document = await createKnowledgeDocument(await readCrmJson(request));
      return Response.json({ document }, { status: 201 });
    });
  } catch (error) {
    return crmConfigurationErrorResponse(error);
  }
}
