import { randomUUID } from "node:crypto";
import type { NextRequest } from "next/server";
import { crmOperationErrorResponse, requireInteger } from "@/lib/crm/api";
import { assertExactKeys, assertObject, parseOptionalText, parseRequiredText, parseUuid, readCrmJson } from "@/lib/crm/categories";
import { updateDraft } from "@/lib/crm/drafts";
import { requireCrmMutationContext, requireIdempotencyKey } from "@/lib/crm/http";
import { parseExtraRecipients } from "@/lib/inbox/replyRequest";
import { sendDraft } from "@/lib/crm/send";
import { runInOrganization } from "@/lib/tenancy/scope";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const value = await readCrmJson(request);
      assertObject(value);
      assertExactKeys(value, ["revision", "subject", "body", "bodyText", "bodyHtml", "cc", "bcc"]);
      const extra = parseExtraRecipients(value.cc, value.bcc);
      const draftId = parseUuid((await params).id, "draft id");
      const originalRevision = requireInteger(value.revision, "revision");
      const hasEditedContent = value.body !== undefined || value.bodyText !== undefined || value.subject !== undefined || value.bodyHtml !== undefined;
      const edited = hasEditedContent ? await updateDraft({
        draftId,
        revision: originalRevision,
        subject: parseOptionalText(value.subject, "subject", 998),
        bodyText: parseRequiredText(value.bodyText ?? value.body, "bodyText", 100_000),
        bodyHtml: parseOptionalText(value.bodyHtml, "bodyHtml", 100_000),
      }) : null;
      const attempt = await sendDraft({
        draftId,
        revision: edited?.revision ?? originalRevision,
        idempotencyKey: requireIdempotencyKey(request.headers),
        requestId: request.headers.get("x-request-id")?.trim() || randomUUID(),
        ccEmails: extra.cc,
        bccEmails: extra.bcc,
      });
      return Response.json({ attempt });
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
