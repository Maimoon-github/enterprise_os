import { NextResponse } from "next/server";

/** Master Inbox drafts are historical; outbound replies are sent from CRM. */
export async function POST() {
  return NextResponse.json(
    { error: "This conversation is owned by CRM; send it from the CRM workspace" },
    { status: 409 },
  );
}
