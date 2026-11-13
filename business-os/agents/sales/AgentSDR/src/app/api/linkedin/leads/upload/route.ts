import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json(
    { ok: false, error: "Use the campaign import flow so CSV columns are reviewed and mapped before People are created" },
    { status: 400 },
  );
}
