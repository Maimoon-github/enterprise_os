import * as XLSX from "xlsx";

const HEADERS = ["Email", "LinkedIn URL", "Full Name", "First Name", "Last Name", "Job Title", "Company", "Company Domain", "Phone", "Notes"];

export async function GET() {
  const sheet = XLSX.utils.aoa_to_sheet([
    HEADERS,
    ["jane.doe@acme.com", "https://www.linkedin.com/in/jane-doe", "Jane Doe", "", "", "Head of Growth", "Acme", "acme.com", "+1 415 555 2671", "Met at conference"],
  ]);
  sheet["!cols"] = HEADERS.map((header) => ({ wch: Math.max(header.length, 20) }));
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, "People");
  const buffer = XLSX.write(workbook, { type: "buffer", bookType: "xlsx" });
  return new Response(buffer, {
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": 'attachment; filename="people-import-template.xlsx"',
    },
  });
}
