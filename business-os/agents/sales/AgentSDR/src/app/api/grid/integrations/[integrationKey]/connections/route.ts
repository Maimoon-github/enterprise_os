import { NextRequest, NextResponse } from "next/server";
import { getIntegration } from "@/lib/integrations/catalog";
import {
  createIntegrationConnection,
  listIntegrationConnections,
} from "@/lib/grid/providers";
import { authContextErrorResponse, requirePermission, withOrgContext } from "@/lib/auth/context";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ integrationKey: string }> },
) {
  try {
    return await withOrgContext(_request, async () => {
      const { integrationKey } = await params;
      if (!getIntegration(integrationKey)) {
        return NextResponse.json({ error: "integration not found" }, { status: 404 });
      }
      return NextResponse.json({ connections: await listIntegrationConnections(integrationKey) });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ integrationKey: string }> },
) {
  try {
    return await withOrgContext(request, async (ctx) => {
      requirePermission(ctx, { integrations: ["manage"] });
      const { integrationKey } = await params;
      let body: { name?: string; credentials?: Record<string, string> };
      try {
        body = await request.json();
      } catch {
        return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
      }

      if (!body.credentials || typeof body.credentials !== "object" || Array.isArray(body.credentials)) {
        return NextResponse.json({ error: "Credentials are required" }, { status: 400 });
      }

      try {
        const connection = await createIntegrationConnection({
          integrationKey,
          name: body.name ?? "",
          credentials: body.credentials,
        });
        return NextResponse.json({ connection }, { status: 201 });
      } catch (error) {
        return NextResponse.json(
          { error: error instanceof Error ? error.message : "Could not add account" },
          { status: 400 },
        );
      }
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
