import { NextRequest, NextResponse } from "next/server";
import { listCampaigns, createCampaign } from "@/lib/outreach/campaigns";
import { withOrgContext, authContextErrorResponse } from "@/lib/auth/context";

// GET /api/outreach/campaigns — list campaigns with lead counts.
export async function GET(request: NextRequest) {
  try {
    return await withOrgContext(request, async () => {
      const rows = await listCampaigns();
      return NextResponse.json({ campaigns: rows });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}

// POST /api/outreach/campaigns — { name }
export async function POST(req: NextRequest) {
  try {
    return await withOrgContext(req, async () => {
      let body: { name?: string };
      try {
        body = await req.json();
      } catch {
        return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
      }
      if (!body.name?.trim()) {
        return NextResponse.json({ error: "name is required" }, { status: 400 });
      }
      const campaign = await createCampaign({ name: body.name });
      return NextResponse.json({ campaign }, { status: 201 });
    });
  } catch (error) {
    const response = authContextErrorResponse(error);
    if (response) return response;
    throw error;
  }
}
