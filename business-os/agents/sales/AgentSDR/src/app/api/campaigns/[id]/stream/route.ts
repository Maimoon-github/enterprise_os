/**
 * GET /api/campaigns/[id]/stream
 *
 * Server-Sent Events observer. This route does not run qualification work.
 * It only streams persisted DB state for a server-owned background job.
 */
import { NextRequest } from "next/server";
import { and, desc, eq } from "drizzle-orm";
import { authContextErrorResponse, withOrgContext } from "@/lib/auth/context";
import { inOrg, runInOrganization } from "@/lib/tenancy/scope";
import { db } from "@/lib/db";
import { campaigns, qualificationJobs } from "@/lib/schema";
import { getCampaignDomains } from "@/lib/qualification";
import { recoverStaleJobs, resumeCampaignJobIfNeeded } from "@/lib/qualification/jobRunner";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function sse(controller: ReadableStreamDefaultController, event: object) {
  const payload = `data: ${JSON.stringify(event)}\n\n`;
  controller.enqueue(new TextEncoder().encode(payload));
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

type CampaignDomainRow = Awaited<ReturnType<typeof getCampaignDomains>>[number];

function toDomainEvent(row: CampaignDomainRow, campaignId: string) {
  return {
    id: row.id,
    domain: row.domain,
    status: row.status,
    isParentCompany: row.isParentCompany,
    checkedAt: row.checkedAt?.toISOString() ?? null,
    allLeadCount: row.allLeadCount ?? null,
    verifiedEmployeeCount: row.verifiedEmployeeCount ?? null,
    revenue: row.revenue,
    parentId: row.parentId,
    parentPending: row.parentPending,
    parentDomain: row.parentDomain,
    parentPreviouslyAdded:
      Boolean(row.parentDomain && row.parentCampaignId && row.parentCampaignId !== campaignId),
    parentCampaignId: row.parentCampaignId,
    reason: row.reason,
    qualificationDebug: row.qualificationDebug,
  };
}

async function latestCampaignJob(campaignId: string) {
  const [job] = await db
    .select()
    .from(qualificationJobs)
    .where(eq(qualificationJobs.campaignId, campaignId))
    .orderBy(desc(qualificationJobs.startedAt))
    .limit(1);
  return job ?? null;
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    return await withOrgContext(req, (ctx) => stream(id, ctx.organizationId));
  } catch (error) {
    const auth = authContextErrorResponse(error);
    if (auth) return auth;
    throw error;
  }
}

/** latestCampaignJob is only called after the campaign was loaded inOrg, so the job is this organization's. */
async function stream(id: string, organizationId: string) {
  const [campaign] = await db
    .select()
    .from(campaigns)
    .where(and(inOrg(campaigns), eq(campaigns.id, id)))
    .limit(1);

  if (!campaign) {
    return new Response(
      `data: ${JSON.stringify({ type: "error", data: { message: "campaign not found" } })}\n\n`,
      { status: 404, headers: { "Content-Type": "text/event-stream" } },
    );
  }

  await recoverStaleJobs();
  await resumeCampaignJobIfNeeded(id);

  // The polling loop outlives the handler's await chain: scope it explicitly.
  const body = new ReadableStream({
    start(controller) {
      return runInOrganization(organizationId, async () => {
      try {
        while (true) {
          const [freshCampaign] = await db
            .select()
            .from(campaigns)
            .where(and(inOrg(campaigns), eq(campaigns.id, id)))
            .limit(1);
          const job = await latestCampaignJob(id);
          const rows = await getCampaignDomains(id);

          sse(controller, {
            type: "all_domains",
            data: rows.map((row) => toDomainEvent(row, id)),
          });

          sse(controller, {
            type: "stats",
            data: {
              accumulated: freshCampaign?.accumulatedLeadCount ?? 0,
              qualified: job?.domainsQualified ?? rows.filter((row) => row.status === "qualified").length,
              processed: job?.domainsProcessed ?? rows.length,
              campaignStatus: freshCampaign?.status ?? "building",
              jobStatus: job?.status ?? null,
              currentDomain: job?.currentDomain ?? null,
            },
          });

          if (!job || job.finishedAt || ["success", "failed", "cancelled"].includes(job.status)) {
            sse(controller, {
              type: "done",
              data: {
                apolloLink: freshCampaign?.apolloLink ?? null,
                stopped: job?.status === "cancelled",
                failed: job?.status === "failed",
              },
            });
            break;
          }

          await sleep(1500);
        }
      } catch (err) {
        sse(controller, {
          type: "error",
          data: { message: err instanceof Error ? err.message : "stream failed" },
        });
      } finally {
        controller.close();
      }
      });
    },
  });

  return new Response(body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
