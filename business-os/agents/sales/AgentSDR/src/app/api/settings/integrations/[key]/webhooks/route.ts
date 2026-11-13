import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse, requirePermission, withOrgContext } from "@/lib/auth/context";
import { isPlatformNotConnectedError, reregisterUnipileWebhooks, revealUnipileWebhookSetup } from "@/lib/platform/credentials";

// Unipile's webhooks, which AgentSDR registers itself when the integration
// is saved (src/lib/platform/unipileWebhooks.ts). Behind the session cookie,
// and limited to people who manage integrations: GET is the one response
// that carries a stored secret, sent only when an admin asks to see it.

type Ctx = { params: Promise<{ key: string }> };

function failure(error: unknown, fallback: string): Response {
  const denied = authContextErrorResponse(error);
  if (denied) return denied;
  if (isPlatformNotConnectedError(error)) return NextResponse.json({ error: error.message }, { status: 409 });
  return NextResponse.json({ error: error instanceof Error ? error.message : fallback }, { status: 400 });
}

// GET /api/settings/integrations/unipile/webhooks — the webhook URLs and the secret, to register by hand.
export async function GET(req: NextRequest, { params }: Ctx) {
  const { key } = await params;
  if (key !== "unipile") return NextResponse.json({ error: "Not found" }, { status: 404 });
  try {
    return await withOrgContext(req, async (ctx) => {
      requirePermission(ctx, { integrations: ["manage"] });
      return NextResponse.json(await revealUnipileWebhookSetup(), { headers: { "Cache-Control": "no-store" } });
    });
  } catch (error) {
    return failure(error, "Could not read the webhook setup");
  }
}

// POST /api/settings/integrations/unipile/webhooks — register the webhooks again.
export async function POST(req: NextRequest, { params }: Ctx) {
  const { key } = await params;
  if (key !== "unipile") return NextResponse.json({ error: "Not found" }, { status: 404 });
  try {
    return await withOrgContext(req, async (ctx) => {
      requirePermission(ctx, { integrations: ["manage"] });
      return NextResponse.json(await reregisterUnipileWebhooks());
    });
  } catch (error) {
    return failure(error, "Could not register the webhooks");
  }
}
