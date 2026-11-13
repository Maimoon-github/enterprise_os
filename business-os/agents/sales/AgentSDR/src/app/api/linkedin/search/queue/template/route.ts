import { NextResponse } from "next/server";
import { buildSearchQueueTemplateBuffer } from "@/lib/linkedin/searchQueueTemplate";

export async function GET() {
  const buffer = buildSearchQueueTemplateBuffer();

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": 'attachment; filename="search-queue-template.xlsx"',
    },
  });
}
