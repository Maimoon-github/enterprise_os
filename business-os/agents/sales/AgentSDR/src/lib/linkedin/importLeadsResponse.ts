import { failedLeadsFilePayload, type FailedLeadExportRow } from "@/lib/linkedin/exportFailedLeads";
import type { ImportLeadsResult } from "@/lib/linkedin/importLeads";

export const buildImportLeadsJsonResponse = (result: ImportLeadsResult) => ({
  ok: true as const,
  created: result.created,
  attached: result.attached,
  failed: result.failed,
  skipped: result.skipped,
  total: result.total,
  ...(result.errors.length ? { errors: result.errors } : {}),
  ...(result.failedRows.length ? { failedRows: result.failedRows } : {}),
  ...(result.crossCampaignNotices.length ? { crossCampaignNotices: result.crossCampaignNotices } : {}),
  ...failedLeadsFilePayload(result.failedRows),
});
