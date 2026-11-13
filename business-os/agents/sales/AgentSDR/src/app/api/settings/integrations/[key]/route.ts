import { NextRequest, NextResponse } from "next/server";
import { authContextErrorResponse, requirePermission, withOrgContext } from "@/lib/auth/context";
import { isPlatformKey } from "@/lib/platform/catalog";
import { disconnectPlatformIntegration, savePlatformIntegration } from "@/lib/platform/credentials";

// Behind the session cookie like every /api route not listed in proxy.ts PUBLIC.
// Responses carry PlatformStatus only — never a secret value.

type Ctx = { params: Promise<{ key: string }> };

// PUT /api/settings/integrations/:key — body: { [fieldKey]: string }. Verifies against the live service, then saves.
export async function PUT(req: NextRequest, { params }: Ctx) {
  const { key } = await params;
  if (!isPlatformKey(key)) return NextResponse.json({ error: "Unknown integration" }, { status: 404 });

  const body: unknown = await req.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  try {
    return await withOrgContext(req, async (ctx) => {
      requirePermission(ctx, { integrations: ["manage"] });
      return NextResponse.json(await savePlatformIntegration(key, body as Record<string, unknown>));
    });
  } catch (error) {
    const denied = authContextErrorResponse(error);
    if (denied) return denied;
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not save the integration" },
      { status: 400 },
    );
  }
}

// DELETE /api/settings/integrations/:key — disconnect.
export async function DELETE(req: NextRequest, { params }: Ctx) {
  const { key } = await params;
  if (!isPlatformKey(key)) return NextResponse.json({ error: "Unknown integration" }, { status: 404 });
  try {
    return await withOrgContext(req, async (ctx) => {
      requirePermission(ctx, { integrations: ["manage"] });
      await disconnectPlatformIntegration(key);
      return NextResponse.json({ ok: true });
    });
  } catch (error) {
    const denied = authContextErrorResponse(error);
    if (denied) return denied;
    throw error;
  }
}
