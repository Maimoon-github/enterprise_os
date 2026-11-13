import { NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { desc } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { linkedInAccounts } from "@/lib/linkedin/schema";

export async function GET(req: Request) {
  return withLinkedinOrg(req, async () => {
    try {
      const accounts = await db
        .select()
        .from(linkedInAccounts)
        .where(inOrg(linkedInAccounts))
        .orderBy(desc(linkedInAccounts.createdAt));
      return NextResponse.json({ ok: true, accounts });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
