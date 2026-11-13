import { NextRequest, NextResponse } from "next/server";
import { withLinkedinOrg } from "@/lib/linkedin/organizations.server";
import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { inOrg } from "@/lib/tenancy/scope";
import { linkedInAccounts } from "@/lib/linkedin/schema";
import { numberRule, ruleError } from "@/lib/channels/rules";
import {
  DEFAULT_WORK_DAYS,
  DEFAULT_WORK_END,
  DEFAULT_WORK_START,
  DEFAULT_WORK_TIMEZONE,
} from "@/lib/linkedin/workingHours";

const HHMM_RE = /^([01]?\d|2[0-3]):([0-5]\d)$/;

type AccountUpdate = {
  dailyInviteLimit?: number | null;
  workTimezone?: string | null;
  workStartTime?: string | null;
  workEndTime?: string | null;
  workDays?: string | null;
};

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return withLinkedinOrg(req, async () => {
    const { id } = await params;

    try {
      const body = await req.json();
      const data: AccountUpdate = {};

      if ("workHoursEnabled" in body) {
        const enabled = Boolean(body.workHoursEnabled);
        if (!enabled) {
          data.workTimezone = null;
          data.workStartTime = null;
          data.workEndTime = null;
          data.workDays = null;
        } else {
          data.workTimezone =
            typeof body.workTimezone === "string" ? body.workTimezone : DEFAULT_WORK_TIMEZONE;
          data.workStartTime =
            typeof body.workStartTime === "string" ? body.workStartTime : DEFAULT_WORK_START;
          data.workEndTime = typeof body.workEndTime === "string" ? body.workEndTime : DEFAULT_WORK_END;
          data.workDays = typeof body.workDays === "string" ? body.workDays : DEFAULT_WORK_DAYS;
        }
      } else {
        if ("workTimezone" in body) {
          data.workTimezone = body.workTimezone === null || body.workTimezone === "" ? null : String(body.workTimezone);
        }
        if ("workStartTime" in body) {
          data.workStartTime = body.workStartTime == null ? null : String(body.workStartTime);
        }
        if ("workEndTime" in body) {
          data.workEndTime = body.workEndTime == null ? null : String(body.workEndTime);
        }
        if ("workDays" in body) {
          data.workDays = body.workDays == null ? null : String(body.workDays);
        }
      }

      if (data.workStartTime && !HHMM_RE.test(data.workStartTime)) {
        return NextResponse.json({ ok: false, error: "workStartTime must be HH:mm" }, { status: 400 });
      }
      if (data.workEndTime && !HHMM_RE.test(data.workEndTime)) {
        return NextResponse.json({ ok: false, error: "workEndTime must be HH:mm" }, { status: 400 });
      }

      // The account's own invitations a day (null = the organization's rule),
      // within the hard ceilings of the rule for its plan.
      if ("dailyInviteLimit" in body) {
        if (body.dailyInviteLimit === null) {
          data.dailyInviteLimit = null;
        } else {
          const [current] = await db
            .select({ isPremium: linkedInAccounts.isPremium })
            .from(linkedInAccounts)
            .where(and(inOrg(linkedInAccounts), eq(linkedInAccounts.id, id)))
            .limit(1);
          if (!current) return NextResponse.json({ ok: false, error: "Account not found" }, { status: 404 });
          const error = ruleError(numberRule("linkedin", current.isPremium ? "invitesPerDayPremium" : "invitesPerDayFree"), body.dailyInviteLimit);
          if (error) return NextResponse.json({ ok: false, error }, { status: 400 });
          data.dailyInviteLimit = body.dailyInviteLimit as number;
        }
      }

      if (Object.keys(data).length === 0) {
        return NextResponse.json({ ok: false, error: "Nothing to update" }, { status: 400 });
      }

      const [account] = await db
        .update(linkedInAccounts)
        .set(data)
        .where(and(inOrg(linkedInAccounts), eq(linkedInAccounts.id, id)))
        .returning();

      // Prisma's update threw (→ 500) when the id did not exist; Drizzle just
      // returns no rows, so keep the same outward behaviour.
      if (!account) {
        return NextResponse.json({ ok: false, error: "Account not found" }, { status: 404 });
      }

      return NextResponse.json({ ok: true, account });
    } catch (err) {
      return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
    }
  });
}
