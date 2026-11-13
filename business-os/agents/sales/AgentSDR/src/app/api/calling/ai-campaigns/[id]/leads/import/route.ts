import type { NextRequest } from "next/server";
import { CrmConfigurationValidationError } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { callApiErrorResponse } from "@/lib/calls/sessions";
import { importAiLeads, previewAiLeadsUpload } from "@/lib/calls/aiCampaigns/campaigns.server";
import { runInOrganization } from "@/lib/tenancy/scope";

const MAX_FILE_BYTES = 20 * 1024 * 1024;

/**
 * Multipart: `file`, then either `mode=preview` (headers, first rows, suggested
 * mapping) or `mapping` (JSON, field key → column header) to import. The shared
 * spreadsheet mapping dialog drives it.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id } = await params;
    let form: FormData;
    try {
      form = await request.formData();
    } catch {
      throw new CrmConfigurationValidationError("Send the spreadsheet as multipart form data");
    }
    const file = form.get("file");
    if (!(file instanceof File)) throw new CrmConfigurationValidationError("No file provided");
    if (file.size > MAX_FILE_BYTES) throw new CrmConfigurationValidationError("The file is too large (max 20 MB)");
    const buffer = await file.arrayBuffer();
    if (form.get("mode") === "preview") {
      return await runInOrganization(ctx.organizationId, async () => Response.json(await previewAiLeadsUpload(id, buffer)));
    }
    const rawMapping = form.get("mapping");
    if (typeof rawMapping !== "string") throw new CrmConfigurationValidationError("Confirm the column mapping before importing");
    let mapping: unknown;
    try {
      mapping = JSON.parse(rawMapping);
    } catch {
      throw new CrmConfigurationValidationError("mapping must be valid JSON");
    }
    return await runInOrganization(ctx.organizationId, async () => Response.json(await importAiLeads(id, buffer, mapping)));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
