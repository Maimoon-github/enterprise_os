import type { NextRequest } from "next/server";
import { assertExactKeys, assertObject, CrmConfigurationValidationError, readCrmJson } from "@/lib/crm/categories";
import { requireCrmMutationContext } from "@/lib/crm/http";
import { withOrgContext } from "@/lib/auth/context";
import { runInOrganization } from "@/lib/tenancy/scope";
import { whatsappApiErrorResponse } from "@/lib/whatsapp/errors";
import { addPeopleToWhatsappCampaign, listWhatsappCampaignLeads } from "@/lib/whatsapp/campaigns/campaigns.server";
import {
  WHATSAPP_CAMPAIGN_LEAD_STATUSES,
  type ListWhatsappCampaignLeadsQuery,
  type WhatsappCampaignLeadStatus,
} from "@/lib/whatsapp/campaigns/contract";

type Params = { params: Promise<{ id: string }> };

function parseNumber(value: string | null, label: string): number | undefined {
  if (value === null || value === "") return undefined;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) throw new CrmConfigurationValidationError(`${label} must be a positive integer`);
  return parsed;
}

function parseQuery(url: URL): ListWhatsappCampaignLeadsQuery {
  const status = url.searchParams.get("status");
  if (status && !(WHATSAPP_CAMPAIGN_LEAD_STATUSES as readonly string[]).includes(status)) {
    throw new CrmConfigurationValidationError(`status must be one of: ${WHATSAPP_CAMPAIGN_LEAD_STATUSES.join(", ")}`);
  }
  return {
    status: (status || undefined) as WhatsappCampaignLeadStatus | undefined,
    q: url.searchParams.get("q") ?? undefined,
    page: parseNumber(url.searchParams.get("page"), "page"),
    pageSize: parseNumber(url.searchParams.get("pageSize"), "pageSize"),
  };
}

export async function GET(request: NextRequest, { params }: Params) {
  try {
    const { id } = await params;
    const query = parseQuery(new URL(request.url));
    return await withOrgContext(request, async () => Response.json(await listWhatsappCampaignLeads(id, query)));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}

export async function POST(request: NextRequest, { params }: Params) {
  try {
    const ctx = await requireCrmMutationContext(request);
    const { id } = await params;
    const body = await readCrmJson(request);
    assertObject(body);
    assertExactKeys(body, ["personIds"]);
    if (!Array.isArray(body.personIds) || body.personIds.some((value) => typeof value !== "string")) {
      throw new CrmConfigurationValidationError("personIds must be an array of ids");
    }
    const personIds = body.personIds as string[];
    return await runInOrganization(ctx.organizationId, async () => Response.json(await addPeopleToWhatsappCampaign(id, personIds)));
  } catch (error) {
    return whatsappApiErrorResponse(error);
  }
}
