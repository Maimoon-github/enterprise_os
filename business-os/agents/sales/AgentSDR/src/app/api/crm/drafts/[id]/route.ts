import type { NextRequest } from "next/server";
import { crmOperationErrorResponse, requireInteger } from "@/lib/crm/api";
import { assertExactKeys, assertObject, parseOptionalText, parseRequiredText, parseUuid, readCrmJson } from "@/lib/crm/categories";
import { discardDraft, updateDraft } from "@/lib/crm/drafts";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { runInOrganization } from "@/lib/tenancy/scope";

async function mutate(request: NextRequest, id: string) {
  const ctx = await requireCrmMutationContext(request);
  return runInOrganization(ctx.organizationId, async () => {
    const value = await readCrmJson(request);
    assertObject(value);
    if (value.status === "discarded") {
      assertExactKeys(value, ["status", "revision"]);
      return { draft: await discardDraft({ draftId: parseUuid(id, "draft id") }) };
    }
    assertExactKeys(value, ["subject", "body", "bodyText", "bodyHtml", "revision"]);
    return { draft: await updateDraft({
      draftId: parseUuid(id, "draft id"),
      revision: requireInteger(value.revision, "revision"),
      subject: parseOptionalText(value.subject, "subject", 998),
      bodyText: parseRequiredText(value.bodyText ?? value.body, "bodyText", 100_000),
      bodyHtml: parseOptionalText(value.bodyHtml, "bodyHtml", 100_000),
    }) };
  });
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try { return Response.json(await mutate(request, (await params).id)); }
  catch (error) { return crmOperationErrorResponse(error); }
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try { return Response.json(await mutate(request, (await params).id)); }
  catch (error) { return crmOperationErrorResponse(error); }
}
