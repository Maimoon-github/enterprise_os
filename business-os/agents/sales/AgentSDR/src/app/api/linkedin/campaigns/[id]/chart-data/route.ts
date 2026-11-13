import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, eq, gte, inArray } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { leads, messages as messagesTable } from "@/lib/linkedin/schema";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(_req, async () => {
    const { id } = await params;

    const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);

    // `lead: { campaignId: id }` was a relation filter — only messages that have
    // a Lead in this campaign match, so this is an inner join.
    const messages = await db
      .select({ type: messagesTable.type, createdAt: messagesTable.createdAt })
      .from(messagesTable)
      .innerJoin(leads, eq(messagesTable.leadId, leads.id))
      .where(
        and(
          inOrg(messagesTable),
          inArray(messagesTable.type, ["INVITATION", "ACCEPTANCE"]),
          eq(leads.campaignId, id),
          gte(messagesTable.createdAt, sevenDaysAgo)
        )
      );

    // Build last-7-days array (today inclusive)
    const days: { date: string; invitations: number; accepted: number }[] = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      days.push({ date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }), invitations: 0, accepted: 0 });
    }

    for (const msg of messages) {
      const label = new Date(msg.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric" });
      const day = days.find((d) => d.date === label);
      if (!day) continue;
      if (msg.type === "INVITATION") day.invitations++;
      else if (msg.type === "ACCEPTANCE") day.accepted++;
    }

    return NextResponse.json({ ok: true, data: days });
  });
}
