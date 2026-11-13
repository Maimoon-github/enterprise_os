import * as XLSX from "xlsx";

export type FailedLeadExportRow = {
  raw: Record<string, string>;
  reason: string;
};

export const FAILED_REASON_COLUMN = "Failed Reason";

export const buildFailedLeadsExcelBuffer = (failedRows: FailedLeadExportRow[]): Buffer => {
  if (failedRows.length === 0) return Buffer.alloc(0);

  const sheetRows = failedRows.map(({ raw, reason }) => ({
    ...raw,
    [FAILED_REASON_COLUMN]: reason,
  }));

  const worksheet = XLSX.utils.json_to_sheet(sheetRows);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Failed");

  return XLSX.write(workbook, { type: "buffer", bookType: "xlsx" }) as Buffer;
};

export const failedLeadsFilePayload = (
  failedRows: FailedLeadExportRow[]
): { failedFileBase64: string; failedFileName: string } | null => {
  const buffer = buildFailedLeadsExcelBuffer(failedRows);
  if (buffer.length === 0) return null;

  return {
    failedFileBase64: buffer.toString("base64"),
    failedFileName: `leads-import-failed-${new Date().toISOString().slice(0, 10)}.xlsx`,
  };
};

/** Build spreadsheet-shaped raw row from API JSON for failed export. */
export const mappedLeadRowToRaw = (row: {
  linkedinUrl: string;
  linkedinApi?: "sales_navigator" | "recruiter" | null;
  email?: string | null;
  name?: string | null;
  headline?: string | null;
  location?: string | null;
  profilePictureUrl?: string | null;
  companyName?: string | null;
  companyDomain?: string | null;
  campaignName?: string | null;
  invitationMessage?: string | null;
  acceptanceMessage?: string | null;
  followUp1Message?: string | null;
  followUp2Message?: string | null;
  followUp3Message?: string | null;
}): Record<string, string> => ({
  "LinkedIn URL": row.linkedinUrl,
  "LinkedIn API": row.linkedinApi ?? "",
  Email: row.email ?? "",
  Name: row.name ?? "",
  Headline: row.headline ?? "",
  Location: row.location ?? "",
  "Profile Picture URL": row.profilePictureUrl ?? "",
  "Company Name": row.companyName ?? "",
  "Company Domain": row.companyDomain ?? "",
  ...(row.campaignName ? { "Campaign Name": row.campaignName } : {}),
  "Invitation Message (max 300 chars)": row.invitationMessage ?? "",
  "Acceptance Message": row.acceptanceMessage ?? "",
  "Follow-up 1": row.followUp1Message ?? "",
  "Follow-up 2": row.followUp2Message ?? "",
  "Follow-up 3": row.followUp3Message ?? "",
});
