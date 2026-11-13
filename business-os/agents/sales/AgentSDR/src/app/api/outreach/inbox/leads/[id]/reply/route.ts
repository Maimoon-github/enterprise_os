import { randomUUID } from "node:crypto";
import type { NextRequest } from "next/server";
import { crmOperationErrorResponse } from "@/lib/crm/api";
import { parseUuid, readCrmJson } from "@/lib/crm/categories";
import { updateDraft } from "@/lib/crm/drafts";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { createManualDraft } from "@/lib/crm/operations";
import { sendDraft } from "@/lib/crm/send";
import { findCrmConversationForInboxContact } from "@/lib/inbox/crmContext.server";
import { parseInboxReplyRequest } from "@/lib/inbox/replyRequest";
import { runInOrganization } from "@/lib/tenancy/scope";

// POST /api/outreach/inbox/leads/[id]/reply
/**
 * Sends a Master Inbox reply through the CRM, so it records as the
 * conversation's sequence step (sendDraft adopts the pending step) and the
 * CRM stays the owner of the thread's state.
 *
 * Body: { subject, text, html?, cc?, bcc?, draftId?, revision? } — cc/bcc are
 * string[] (reply-all); `to` is ignored, the contact is always the To. With `draftId` the
 * existing CRM draft is edited and sent; without it a manual draft is created
 * on the contact's CRM email conversation. Other keys (incl. to) are ignored.
 * Responds { attempt } on success; 404 when the contact has no active CRM
 * email conversation; 409 with the CRM's message on conflicts.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    return await runInOrganization(ctx.organizationId, async () => {
      const contactId = parseUuid((await params).id, "contact id");
      const body = parseInboxReplyRequest(await readCrmJson(request));
      const idempotencyKey = request.headers.get("idempotency-key")?.trim() || randomUUID();
      const requestId = request.headers.get("x-request-id")?.trim() || randomUUID();

      let draft: { id: string; revision: number };
      if (body.draft) {
        draft = await updateDraft({
          draftId: body.draft.id,
          revision: body.draft.revision,
          subject: body.subject,
          bodyText: body.text,
          bodyHtml: body.html,
        });
      } else {
        const conversation = await findCrmConversationForInboxContact(contactId);
        if (!conversation) {
          return Response.json(
            { error: "This contact has no active CRM email conversation to reply on", code: "NOT_FOUND" },
            { status: 404 },
          );
        }
        draft = await createManualDraft({
          recordId: conversation.recordId,
          conversationId: conversation.id,
          subject: body.subject,
          bodyText: body.text,
          bodyHtml: body.html,
        });
      }

      const attempt = await sendDraft({
        draftId: draft.id,
        revision: draft.revision,
        idempotencyKey,
        requestId,
        ccEmails: body.cc,
        bccEmails: body.bcc,
      });
      return Response.json({ attempt });
    });
  } catch (error) {
    return crmOperationErrorResponse(error);
  }
}
