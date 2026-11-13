import { NextResponse } from "next/server";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { getByokSettings } from "@/lib/ai/byok";
import { resolveParentDomain } from "@/lib/qualification/parentLookup";

export async function GET(request: Request) {
  try {
    return await withOrgContext(request, async () => {
    const parentDomain = await resolveParentDomain("kiehls.com");
    const settings = await getByokSettings();
    return NextResponse.json({
      parentDomain,
      openRouter: {
        configured: Boolean(settings.connectionId && settings.byokOnlyConfirmed),
        model: settings.defaultModel,
      },
    });
    });
  } catch (e) {
    const denied = authContextErrorResponse(e);
    if (denied) return denied;
    return NextResponse.json({ fetchError: String(e) });
  }
}
