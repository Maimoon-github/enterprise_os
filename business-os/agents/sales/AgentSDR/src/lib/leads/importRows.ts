import * as XLSX from "xlsx";
import type { ManualPersonInput } from "./manualImport";

/**
 * The CSV/XLSX row parsing shared by every importer that produces
 * ManualPersonInput rows: the People import
 * (src/app/api/leads/people/import/route.ts) and the Calling campaign
 * contacts import (src/app/api/calling/campaigns/[id]/contacts/import/route.ts).
 * Header aliasing must stay identical between the two, so a file behaves the
 * same way wherever it's uploaded — that's the whole reason this is shared
 * rather than copied.
 *
 * Deliberately returns every row, unfiltered: the two callers disagree on
 * what makes a row usable (People requires an Email or LinkedIn URL; Calling
 * requires a phone number instead), so filtering is each caller's job.
 */

const normalizedHeader = (value: unknown) => String(value ?? "").trim().toLowerCase().replace(/[^a-z0-9]/g, "");
const cell = (value: unknown) => String(value ?? "").trim() || null;

export function parseImportRows(buffer: ArrayBuffer): ManualPersonInput[] {
  const workbook = XLSX.read(buffer, { type: "buffer" });
  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  if (!sheet) throw new Error("The file has no worksheet");
  const values = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1, blankrows: false });
  if (!values.length) throw new Error("The worksheet is empty");
  const headers = values[0].map(normalizedHeader);
  const at = (row: unknown[], names: string[]) => {
    const index = headers.findIndex((header) => names.includes(header));
    return index < 0 ? null : cell(row[index]);
  };
  return values.slice(1).map((row) => ({
    email: at(row, ["email", "emailaddress"]),
    linkedinUrl: at(row, ["linkedin", "linkedinurl", "linkedinprofile"]),
    fullName: at(row, ["name", "fullname"]),
    firstName: at(row, ["firstname"]),
    lastName: at(row, ["lastname"]),
    title: at(row, ["title", "jobtitle", "headline"]),
    companyName: at(row, ["company", "companyname"]),
    companyDomain: at(row, ["domain", "companydomain", "website", "companywebsite", "companyurl"]),
    notes: at(row, ["notes"]),
    phone: at(row, ["phone", "phonenumber", "mobile", "mobilephone", "mobilenumber", "whatsapp", "whatsappnumber", "workphone"]),
  }));
}
