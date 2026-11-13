import { isPlatformConnected } from "@/lib/platform/credentials";
import { NextRequest } from "next/server";
import { db } from "@/lib/db";
import { webhookEvents } from "@/lib/linkedin/schema";
import {
  claimWebhookEvent,
  markInternalWebhookReplay,
  replayableWebhookEvents,
} from "@/lib/linkedin/webhooks/inbox";
import { POST as processConnectionAccepted } from "@/app/api/webhooks/connection-accepted/route";
import { POST as processMessageReceived } from "@/app/api/webhooks/message-received/route";
import { and, eq } from "drizzle-orm";
import { inOrg, runInOrganization } from "@/lib/tenancy/scope";

type ReplaySummary = {
  candidates: number;
  claimed: number;
  succeeded: number;
  failed: number;
};

/**
 * Reprocess errored deliveries and processing rows whose lease was abandoned.
 * Event claiming is independent of outbound pause controls: inbound state must
 * remain recoverable during a People migration. The route-level guard still
 * prevents an automated acceptance send while LinkedIn outbound is paused.
 */
export async function replayLinkedinWebhooks(limit = 100, organizationId?: string): Promise<ReplaySummary> {
  // One global queue; each delivery replays inside its own organization's
  // scope (the handlers also resolve the organization from the payload).
  const events = await replayableWebhookEvents(limit, new Date(), organizationId);
  const summary: ReplaySummary = { candidates: events.length, claimed: 0, succeeded: 0, failed: 0 };
  const unipileByOrg = new Map<string, boolean>();

  for (const { id, organizationId } of events) {
    await runInOrganization(organizationId, async () => {
      let connected = unipileByOrg.get(organizationId);
      if (connected === undefined) {
        connected = await isPlatformConnected("unipile");
        unipileByOrg.set(organizationId, connected);
      }
      if (!connected) {
        console.log(`[replayLinkedinWebhooks] Unipile is not connected for organization ${organizationId} — skipping`);
        return;
      }

      const event = await claimWebhookEvent(id);
      if (!event) return;
      summary.claimed += 1;

      try {
        const body = event.rawBody as Record<string, unknown>;
        const route = event.event === "new_relation" ? processConnectionAccepted : processMessageReceived;
        const request = new NextRequest(`http://internal/api/webhooks/${event.event}`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(body),
        });
        markInternalWebhookReplay(request, event.id);
        const response = await route(request);
        const [outcome] = await db
          .select({ status: webhookEvents.processingStatus })
          .from(webhookEvents)
          .where(and(inOrg(webhookEvents), eq(webhookEvents.id, event.id)))
          .limit(1);
        if (response.ok && (outcome?.status === "ok" || outcome?.status === "skipped")) {
          summary.succeeded += 1;
        } else {
          summary.failed += 1;
        }
      } catch (error) {
        // Route handlers persist their own error state. This fallback covers an
        // exception before a handler can do so (for example request construction).
        await db
          .update(webhookEvents)
          .set({
            processingStatus: "error",
            processingStartedAt: null,
            nextAttemptAt: new Date(Date.now() + 60_000),
            processingLog: [{
              level: "error",
              message: error instanceof Error ? error.message : String(error),
              time: new Date().toISOString(),
            }],
          })
          .where(and(inOrg(webhookEvents), eq(webhookEvents.id, event.id)));
        summary.failed += 1;
      }
    });
  }

  return summary;
}
