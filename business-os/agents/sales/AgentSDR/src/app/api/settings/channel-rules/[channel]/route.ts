import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse, requirePermission, withOrgContext } from "@/lib/auth/context";
import { isChannel } from "@/lib/channels/rules";
import { channelRulesForSettings, saveChannelRules } from "@/lib/channels/rules.server";

// Sending rules for one channel (src/lib/channels/rules.ts). Every member can
// read them; changing them takes the integrations permission (owners, admins).

type Ctx = { params: Promise<{ channel: string }> };

function failure(error: unknown, fallback: string): Response {
  const denied = authContextErrorResponse(error);
  if (denied) return denied;
  return NextResponse.json({ error: error instanceof Error ? error.message : fallback }, { status: 400 });
}

// GET /api/settings/channel-rules/:channel — { values, customized }
export async function GET(req: NextRequest, { params }: Ctx) {
  const { channel } = await params;
  if (!isChannel(channel)) return NextResponse.json({ error: "Unknown channel" }, { status: 404 });
  try {
    return await withOrgContext(req, async () => NextResponse.json(await channelRulesForSettings(channel)));
  } catch (error) {
    return failure(error, "Could not read the sending rules");
  }
}

// PUT /api/settings/channel-rules/:channel — body: { [ruleKey]: value }; returns { values, customized }
export async function PUT(req: NextRequest, { params }: Ctx) {
  const { channel } = await params;
  if (!isChannel(channel)) return NextResponse.json({ error: "Unknown channel" }, { status: 404 });
  const body: unknown = await req.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }
  try {
    return await withOrgContext(req, async (ctx) => {
      requirePermission(ctx, { integrations: ["manage"] });
      return NextResponse.json(await saveChannelRules(channel, body as Record<string, unknown>, ctx.userId));
    });
  } catch (error) {
    return failure(error, "Could not save the sending rules");
  }
}
