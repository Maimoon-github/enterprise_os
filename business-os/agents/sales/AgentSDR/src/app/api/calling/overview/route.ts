import type { NextRequest } from "next/server";
import { getCallingOverview, resolveTimeZone } from "@/lib/calls/overview";
import { isDateString, listDays, MAX_OVERVIEW_RANGE_DAYS } from "@/lib/calls/overviewContract";
import { callApiErrorResponse, CallApiError } from "@/lib/calls/sessions";
import { withOrgContext } from "@/lib/auth/context";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * GET /api/calling/overview?from=YYYY-MM-DD&to=YYYY-MM-DD[&campaignId=uuid][&tz=Area/City]
 * Proxy-gated like every other GET under /api (src/proxy.ts only exempts the
 * listed public prefixes), so no extra auth check here.
 */
export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams;
    const from = params.get("from") ?? "";
    const to = params.get("to") ?? "";
    if (!isDateString(from) || !isDateString(to)) throw new CallApiError(400, "from and to must be dates as YYYY-MM-DD");
    if (from > to) throw new CallApiError(400, "from must not be after to");
    if (listDays(from, to).length > MAX_OVERVIEW_RANGE_DAYS) {
      throw new CallApiError(400, `The range can be at most ${MAX_OVERVIEW_RANGE_DAYS} days`);
    }
    const campaignId = params.get("campaignId") || null;
    if (campaignId && !UUID_RE.test(campaignId)) throw new CallApiError(400, "campaignId must be a UUID");
    const timeZone = resolveTimeZone(params.get("tz"));
    return await withOrgContext(request, async () => Response.json(await getCallingOverview({ from, to, campaignId, timeZone })));
  } catch (error) {
    return callApiErrorResponse(error);
  }
}
