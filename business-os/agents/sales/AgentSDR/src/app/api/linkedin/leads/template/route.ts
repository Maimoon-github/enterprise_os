import { NextResponse } from "next/server";
import { buildLeadsTemplateBuffer } from "@/lib/linkedin/leadsTemplate";

export async function GET() {
  const buffer = buildLeadsTemplateBuffer();

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": 'attachment; filename="leads-template.xlsx"',
    },
  });
}
